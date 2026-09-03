# Dataset and spec wiring

## Establish the dataset contract

Find real labeled examples in local evals, tests, JSONL/CSV files, API fixtures,
or uploaded datasets. Treat existing tests and fixtures as read-only evidence;
never edit or repurpose them for Beaker. For the selected task, identify:

- input shape;
- expected/ground-truth shape;
- prediction fields;
- scoring rules and weights, confirmed by the developer when the
  repository does not already establish them, or when it's unclear which
  metric to use;
- train and test examples (train is the optimization pool; test is held out);
- stable row identifiers and optional grouping/metadata.

Declare the matching JSON Schema through the loader/spec so uploads can be validated. A `Case` is one evaluation example: input plus expected values. Do not infer labels, conventions, edge cases, split composition, or the quality metric to hill-climb from application code or prose.
When several plausible scored fields are found, ask the developer which metric to optimize as soon as possible, but keep replacing `TODO(beaker)`, wiring `_run_case`, and preparing dataset conversion while waiting; insert the chosen field into the scorer when the answer arrives.

If local data is unavailable, inspect hosted data with `beaker dataset list` and
`beaker dataset show`. Validate a usable hosted snapshot with `beaker run smoke
--strict --agent <selected-agent> --dataset <name@revision>` or
`--dataset-id <artifact-id>`. If neither source has usable labels, direct the
developer to upload or provide real examples and stop before finalizing the
spec, running smoke validation, or uploading synthetic data.

## Select one dataset source

For hosted onboarding, retain the uploaded immutable `name@revision` or artifact
id in the current session and pass the same selector explicitly to smoke and
launch:

```bash
beaker run smoke --strict --dataset invoices@<revision>
beaker run trigger --dataset invoices@<revision>
```

Do not commit an organization-specific `dataset_ref` or `dataset_id` to YAML by
default. A repository may intentionally opt into a dataset default when it is
tied to one Beaker organization; explicit `--dataset` or `--dataset-id` flags
still override it. Use `local_dataset_path` only for a real path that will
remain available in the local checkout. Never place Beaker-owned S3 or
presigned URLs in configuration.

## Convert without persisting generated datasets

When real labeled source data must be converted to Beaker's JSONL layout, keep
the conversion script under `.beaker/` and write its generated splits only to an
OS-managed temporary directory. Run the CLI upload synchronously inside the
temporary-directory context so cleanup happens after the CLI has finished
reading the files. If pre-upload local validation is needed, run it in that
same context. After upload, validate the retained immutable remote selector.
Never write generated JSONL into the repository, `.beaker/`, an existing
fixture directory, or another persistent output directory.

Use `tempfile.TemporaryDirectory()` instead of an open `NamedTemporaryFile`, so
the Beaker subprocess can reopen the files reliably across platforms:

```python
import json
import subprocess
import tempfile
from pathlib import Path


with tempfile.TemporaryDirectory(prefix="beaker-dataset-") as temp_dir:
    dataset_dir = Path(temp_dir)
    splits = {"train": train_rows, "test": test_rows}

    for split_name, rows in splits.items():
        split_path = dataset_dir / f"{split_name}.jsonl"
        with split_path.open("w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row) + "\n")

    upload = subprocess.run(
        [
            "beaker", "dataset", "upload", str(dataset_dir),
            "--name", dataset_name,
            "--total-count", str(sum(len(rows) for rows in splits.values())),
            "--split", f"train={len(train_rows)}",
            "--split", f"test={len(test_rows)}",
            "--agent", agent_key,
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(upload.stdout)
    dataset_ref = f"{artifact['artifact_key']}@{artifact['dataset_revision']}"

subprocess.run(
    [
        "beaker", "run", "smoke", "--strict",
        "--agent", agent_key,
        "--dataset", dataset_ref,
    ],
    check=True,
)
```

The CLI currently requires a dataset directory or JSONL file path; this staging
is temporary filesystem materialization, not a repository artifact. Do not add
generated dataset paths to `.gitignore` as a substitute for temporary storage.
If validation must happen before upload, run local smoke against `dataset_dir`
inside the temporary-directory context. The post-upload remote smoke remains
the authoritative check that the hosted snapshot can be downloaded and parsed.

## Map repository code into the spec

Keep the spec and helper code under `.beaker/`. Import the application's
public or existing internal interfaces from the spec; do not create Beaker
orchestration modules in the application package. Never create or modify test
files, fixtures, snapshots, helpers, or test configuration for Beaker, never run
the repository's test suite during onboarding, and never add CI/CD automation
that exercises the spec; `beaker_spec.py` ships without a test of its own.

| Spec component | Repository source of truth |
|---|---|
| `@spec(repository=...)` | Eligible ordinary source files Beaker may improve; omitted means `"all"` |
| `_run_case` | Real async application evaluation path; repository mode receives `targets=None` |
| scorer | Prediction and ground-truth fields plus objective weights; it remains immutable under `.beaker/` |
| `llm_scorer_model` | Optional fixed canonical `provider:model` for an LLM judge; omit for deterministic scoring |
| data loader | Real labeled rows and their validation contract |
| `spec.required_env` | Names of application variables needed during candidate evaluation; never their values |

Keep `CaseResult.output` limited to prediction fields the scorer reads. Put
trajectories, tool history, end state, and other diagnostic evidence in
`CaseResult.context`; do not duplicate large evidence in both. Both values must
remain JSON-normalizable across the evaluator process boundary.

Keep `score_case` async because Beaker awaits it, even for deterministic scoring. Use `objective_score(..., field_weights=...)` when fields have different importance.

### Declare the output kind and emit per-case checks

Beaker's sample-level view does not compare `output` to the expected row
itself; it renders what the spec declares. Two contract fields drive it:

- `CaseResult(output=..., output_kind=...)`, one of `"record"` (a structured
  dict compared field by field to an expected record), `"value"` (one short
  answer), `"text"` (long documents; a dict becomes one expandable card per
  string leaf), or `"none"` (the agent produced no answer and is graded on side
  effects; pass `output=None`). Never place scores, assertion results, or end
  state in `output`; scores go in `CaseScore`, evidence in `context`.
- `CaseScore(..., checks=(Check(...), ...))`: one `Check` per thing the scorer
  verified, passing ones included. `checks` is separate from `field_scores`:
  `field_scores` is the small, stable set of run-level metrics aggregated across
  cases; `checks` is the per-case explanation and its names are never
  aggregated. Map the repository's own vocabulary onto it without adding new
  fields:

  `name`/`description` say what the check is; `expected`/`predicted`/`message`
  say what the prediction did. Never put the check's definition (a criterion
  sentence) in `expected`.

  | Scorer verifies | `name` | `description` | `verdict` | `expected` / `predicted` | `message` | `group` |
  |---|---|---|---|---|---|---|
  | A field of a record | field name | omit | `"pass"`/`"fail"` | both values | why they differ, if known | omit |
  | A rubric criterion judged by an LLM | criterion title | the criterion text the judge was given | `"pass"`/`"fail"` | omit | the judge's comment | deliverable or document name |
  | An assertion on end state | assertion type and target | assertion parameters, if useful | `"pass"`/`"fail"` | both values when the assertion compares one; otherwise omit | assertion failure detail | app or system name |
  | A graded metric (F1, recall, partial credit) | metric name | omit | float in `[0, 1]` | omit | how the score was obtained | omit |

  Set `informational=True` on checks that are computed but do not count toward
  the objective (zero-weight metrics, assertions excluded from scoring); they
  render muted and are left out of the failed-check count.

  Limits: the hosted view keeps at most 100 checks per case and trims to 10
  when the case's evidence response exceeds 256 KB, and `expected`/`predicted`
  are shown as JSON text, not a structured diff. Do not emit one check per row
  of a large table; check the aggregate and put the detail in `message`.

```python
from beaker import CaseResult, CaseScore, Check

async def run_case(self, *, case, targets=None) -> CaseResult:
    state = await run_agent(case.input)
    return CaseResult(output=None, output_kind="none", context={"end_state": state})

async def score_case(self, *, case, result) -> CaseScore:
    outcomes = evaluate_assertions(case, result.context["end_state"])
    checks = tuple(
        Check(
            name=f"{o.type} {o.target}",
            verdict="pass" if o.passed else "fail",
            expected=o.expected,
            predicted=o.observed,
            message=o.detail,
            group=o.app,
            informational=o.excluded,
        )
        for o in outcomes
    )
    scored = [o for o in outcomes if not o.excluded]
    partial = sum(o.passed for o in scored) / len(scored) if scored else 0.0
    return CaseScore(
        objective=partial,
        field_scores={"task_completed_correctly": float(all(o.passed for o in scored)), "partial_credit": partial},
        checks=checks,
    )
```

Repository-mode case inputs and `CaseResult.output`/`context` cross a process
boundary and must be JSON-normalizable. The candidate process receives input
without labels. The trusted controller retains ground truth and invokes the
scorer after the candidate returns.

Distinguish execution failure from a bad answer:

- Return `CaseResult.failed(error, retryable=...)` for harness, dependency, or infrastructure failures that prevented execution.
- Return `CaseResult(output=...)` when the application ran, even when output is empty or incorrect.
- Do not convert every exception into an error-shaped output object.

## Prove repository candidate execution

Inspect the import path from `_run_case` into the real model call. The default
optimization evaluates each proposed repository copy in a fresh process and imports
ordinary application modules from that candidate. Keep the spec, loader,
runner, scorer, evidence provider, and finalizer under `.beaker/`; do not place
candidate implementation there. Use `beaker run smoke --strict` to validate the
structural wiring; it does not execute the runner or prove candidate imports.
When runtime proof is needed, exercise the repository's existing application
or evaluation path under a local Beaker capture and inspect it with
`beaker trace doctor --require-model-calls` and `beaker trace inspect`; do not
add tests, test doubles, or a pipeline job.

The default `@spec()` scope is all eligible ordinary UTF-8 source. Use
`repository=("path", ...)` when the developer wants a smaller source-relative
surface. Hidden paths, `.beaker`, dependency manifests, lock files, build
configuration, vendored source, and binary files are protected. Repository
mode has no `seed_targets`, passes `targets=None`, and reserves TEST evaluation
for the selected winner.

For a logical-target spec, preserve explicit `@spec(repository=None)`. That mode
requires real `Spec.seed_targets`; inspect each prompt or named resource path into
the application exactly as before.

Do not place datasets under `.beaker/`. Existing labeled data is source material,
not Beaker-owned tooling: leave it in its established location and reference it
from the config or command. Generated JSONL conversions exist only in an
OS-managed temporary directory for validation/upload. `.beaker/` owns Beaker
config, specs, helper code, conversion scripts, credentials, and local trace
receipts, but not generated dataset outputs.
