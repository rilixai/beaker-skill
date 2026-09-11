# Dataset and integration wiring

## Establish the dataset contract

Find real labeled examples in local evals, tests, JSONL/CSV files, API fixtures,
or uploaded datasets. Treat existing tests and fixtures as read-only evidence;
never edit or repurpose them for Beaker. For the selected task, identify:

- input shape. The case's `input` is what the sample view shows as the ask,
  so it must carry what the agent was actually given (the task prompt, the
  question, the document reference), not only a lookup key the runner
  resolves internally;
- expected/ground-truth shape. `Case.expected` accepts JSON values; the typed
  row model defines the task's actual shape, including strings, arrays or objects.
  For rubric-, assertion-, or judge-scored tasks, put the known requirements in
  `expected`. An object such as `{"assertions": [...]}` or `{"criteria": [...]}`
  makes the meaning explicit, but is a convention, not an SDK restriction. Do not
  upload `expected: {}` when requirements exist at dataset-build time. When they
  only exist inside the runner (a simulator's own assertions), `expected: {}`
  is correct and the checks come from the JSON application result in `output`;
- prediction fields;
- scoring rules and weights, confirmed by the developer when the
  repository does not already establish them, or when it's unclear which
  metric to use;
- train and test examples (train is the optimization pool; test is held out);
- stable row identifiers and optional labels: `metadata` keys such as domain
  or practice area; `group_key` is only an optional dataset column.

Declare the matching typed `run_setup.row_model`; Beaker derives its JSON Schema to validate dataset rows. A `Case` is one evaluation example: input plus expected values. Do not infer labels, conventions, edge cases, split composition, or the quality metric to hill-climb from application code or prose.
When several plausible scored fields are found, ask the developer which metric to optimize as soon as possible, but keep replacing `TODO(beaker)`, wiring `run_case`, and preparing dataset conversion while waiting; insert the chosen field into the scorer when the answer arrives.

If local data is unavailable, inspect hosted data with `beaker dataset list` and
`beaker dataset show`. Validate a usable hosted snapshot with `beaker run smoke
--strict --integration-id <id> --agent <selected-agent> --dataset <name@revision>` or
`--dataset-id <artifact-id>`. If neither source has usable labels, direct the
developer to upload or provide real examples and stop before finalizing the
integration, running smoke validation, or uploading synthetic data.

## Select one dataset source

For hosted onboarding, retain the uploaded immutable `name@revision` or artifact
id in the current session and pass the same selector explicitly to smoke and
launch:

```bash
beaker run smoke --strict --integration-id <id> --agent <selected-agent> --dataset invoices@<revision>
beaker run trigger --integration-id <id> --agent <selected-agent> --dataset invoices@<revision>
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
the Beaker subprocess can reopen the files reliably across platforms. Reuse the
selected `integration_id` and `agent_key`:

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
        "--integration-id", integration_id,
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

## Map application code into the Integration

Keep the integration, loader, scorer and evaluation helpers under `.beaker/`.
Do not add tests or CI/CD to the consumer repository. The platform owns dataset
I/O and lifecycle; the integration owns row-to-case conversion and application
execution. See [repository_integration.py](repository_integration.py) and
[document_integration.py](document_integration.py) for executable contract scaffolds.
These illustrate wiring only; use the customer's actual application and labeled
rows rather than their demonstration applications and exact-match scorers. Keep the
`TODO(beaker)` markers until the corresponding hooks are implemented; unchanged
examples must remain `SCAFFOLD` under `beaker run smoke --strict`.

| Component | Source of truth |
|---|---|
| `Integration.targets` | Eligible repository paths or declared document groups |
| `run_setup.row_model` | The actual labeled row schema, validated by Pydantic |
| `prepare_run` | Case-loading/document-setup clients and seed documents, held open for the attempt |
| `load_cases` | Async row-to-case conversion; JSON inputs and expected values |
| `run_case(case_input, runtime)` | Real async application path |
| `score_case(case, result, case_files_dir)` | Agreed objective, checks and field metrics |
| Launch `scorer_model` | Fixed canonical model when using an LLM judge; per run or in optional `config_defaults` |
| `integrations.<id>.required_env` | Names of variables used by setup and evaluation |

Return the JSON application result in `CaseResult.output`, including the observed
application state that the scorer needs. Output is retained as the prediction in
result artifacts and can appear in the sample view; it is not private scratch
space for scoring. Keep it compact: select the needed fields instead of returning
an entire framework state object, and avoid duplicating large model/tool payloads
already captured in `runtime.trace`. Scores and concise diagnoses go in `CaseScore`.
`CaseResult` accepts only `output` and optional `output_kind`; do not add a
second evidence or telemetry payload. `score_case` reads `case.expected`,
`result.output`, and staged input files through its `case_files_dir` argument.

A `RunSetup` subclass declares `row_model`, implements async-generator
`load_cases(row, *, runtime)`, and may use the attempt-scoped `SetupRuntime`.
Beaker enters `prepare_run`, then loads cases, and closes resources on success,
failure or cancellation. It validates all raw rows before entering setup.
Never enter the lifecycle context managers yourself. A retry gets a fresh
setup instance. `runtime.config` contains the launch `extra` mapping, not the
whole platform run configuration.

For repository targets, setup and scoring run in the trusted controller while
`run_case` imports each candidate's application source in a fresh evaluator
process. A client stored on the setup instance can serve `load_cases`; it is not
available in the candidate process. Pass JSON inputs and staged `CaseFile` values
across this boundary, then read files through `runtime.case_files_dir` in the
runner or `case_files_dir` in the scorer. Do not pass live clients, absolute
setup-machine paths, or module globals as a substitute for staged input files.

For documents, setup returns actual `TargetDocument` content in declared groups.
Use stable source IDs and preserve source versions. `open_candidate` can build
an index from `targets_dir` using `scratch_dir`; its result becomes
`RolloutRuntime.candidate_runtime`. Build it from the current candidate tree,
including created documents and excluding deleted ones; do not reuse a seed-only
index or assume every seed filename still exists. Keep temporary index files in
`scratch_dir` and close candidate resources when `open_candidate` exits.
Candidate changes return as a `ChangeSet`.
A `ChangeSet` identifies the run, seed hash, candidate hash and ordered
`changes`. Delivery preserves the customer's source identity:

| Operation | Fields and application rule |
|---|---|
| `CreateDocumentChange` | `group`, `name`, `content`; create only if the destination is still absent |
| `UpdateDocumentChange` | `source_id`, `group`, `name`, replacement `content`, `base_sha256`, optional `base_version`; update only if the current source still matches the base |
| `DeleteDocumentChange` | `source_id`, `group`, `name`, `base_sha256`, optional `base_version`; delete only if the current source still matches the base |

The hosted candidate delivery includes `document-change-set.json`. The customer
reviews it and decides when to apply it. Keep stable source IDs and versions in
seed documents so updates can detect intervening edits. Do not treat a document
winner as a repository patch or silently write it back during onboarding.


### Declare the output kind and emit per-case checks

`CaseScore.checks` is what the optimizer's proposer reads to diagnose why a
case failed. Without checks (or scorer-authored `field_diffs`) it sees only
scalar scores and its proposals degrade to generic advice. Beaker's
sample-level view likewise does not compare `output` to the expected row
itself; it renders what the integration declares. Two contract fields drive both:

- `CaseResult(output=..., output_kind=...)` describes the JSON application
  result. Use `record` for structured results, `value` for a short answer,
  `text` for long text (a dictionary becomes one expandable card per string
  leaf), or `none` with `output=None` when no application output is returned.
  Include observed application state in `output` when the scorer needs it;
  keep telemetry in `runtime.trace` and scores in `CaseScore`.
- `CaseScore.checks` explains individual outcomes: emit one check per verified
  field, criterion or assertion, passing ones included. The scorer compares
  `case.expected` with `result.output` and may inspect staged input files.
  `field_scores` is the small stable set aggregated at run level; check names
  are never aggregated.

  `name`/`description` say what the check is; `expected`/`predicted`/`message`
  say what the prediction did. Never put the check's definition (a criterion
  sentence) in `Check.expected`. A check must be readable without the dataset
  row or the runner's internals open: when the requirement refers to things by
  opaque identifiers (record ids, row numbers, file hashes) and the scorer
  already holds state that names them (the initial or observed end state, a
  document manifest), put those names in `name` instead of the ids; a
  deterministic boolean assertion has no `expected`/`predicted` pair, so its
  `name` and `description` carry the whole meaning; do not repeat the same
  values in both. Keep rows short: one line each for `name` and `description`.
  Ten rows that differ only in an id are
  ten indistinguishable rows; when no such state exists, leave the ids and
  explain the scoring in the recipe's README instead.

  | Scorer verifies | `name` | `description` | `verdict` | `expected` / `predicted` | `message` | `group` |
  |---|---|---|---|---|---|---|
  | A field of a record | field name | omit | `"pass"`/`"fail"` | both values | why they differ, if known | omit |
  | A rubric criterion judged by an LLM | criterion title | the criterion text the judge was given | `"pass"`/`"fail"` | omit | the judge's per-criterion comment (have the judge return one; a bare per-criterion pass/fail is the minimum) | deliverable or document name |
  | An assertion on end state | assertion type and its parameters, ids replaced by names (`member_exists · Jane Doe · Q1 Webinar`) | omit when `name` already carries every parameter; otherwise one line naming what the assertion verifies | `"pass"`/`"fail"` | omit; a boolean assertion has none, and the value it compares against is already in `name` | assertion failure detail, or why it is excluded | app or system name |
  | A graded metric (F1, recall, partial credit) | metric name | omit | float in `[0, 1]` | omit | how the score was obtained | omit |

  Set `informational=True` on checks that are computed but do not count toward
  the objective (zero-weight metrics, assertions excluded from scoring); they
  render muted and are left out of the failed-check count. Say why in
  `message` (excluded by the task author, or already true before the agent
  acted), since the two mean different things to a reader.

  Make `message` carry the diagnosis a reader cannot get from the verdict
  alone. When the scorer also holds the initial state, evaluate each
  requirement against it too: a failed requirement that held initially is a
  regression ("held in the initial state; broken by the run"), not a
  never-satisfied one, and the optimizer treats those differently.

  Limits: the hosted view keeps at most 100 checks per case and trims to 10
  when the case's evidence response exceeds 256 KB, and `expected`/`predicted`
  are shown as JSON text, not a structured diff. Do not emit one check per row
  of a large table; check the aggregate and put the detail in `message`.

  `beaker run smoke` does not execute `run_case` or `score_case`, so it cannot
  confirm that checks are emitted; inspect a scored case from the first run.

Keep `score_case` async even for deterministic scoring. Its objective is the
value the optimizer maximizes; choose it from the task's established evaluation
policy. `objective_score` can combine normalized field scores using explicit
weights. For example, if the task already specifies 3:1 weighting:

```python
from beaker import CaseScore, Check, objective_score

def weighted_score(*, correctness: float, completeness: float) -> CaseScore:
    fields = {"correctness": correctness, "completeness": completeness}
    return CaseScore(
        objective=objective_score(
            fields, field_weights={"correctness": 3.0, "completeness": 1.0}
        ),
        field_scores=fields,
        checks=tuple(Check(name=name, verdict=value) for name, value in fields.items()),
    )
```

Those weights are illustrative, not defaults. Use the agreed weights; do not
silently average every diagnostic metric into the objective. Values in
`CaseScore.objective` and `field_scores` must be finite and in `[0, 1]`.

```python
from beaker import CaseResult, CaseScore, Check

async def run_case(*, case_input, runtime) -> CaseResult:
    state = await run_agent(case_input)
    return CaseResult(output={"end_state": state}, output_kind="record")

async def score_case(*, case, result, case_files_dir) -> CaseScore:
    end_state = result.output["end_state"]
    outcomes = evaluate_assertions(case.expected, end_state)
    names = record_names(initial_state_for(case), end_state)  # id -> "Jane Doe"
    checks = tuple(
        Check(
            name=" · ".join([o.type, *(names.get(v, v) for v in o.params.values())]),
            verdict="pass" if o.passed else "fail",
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

Repository-mode case inputs and `CaseResult.output` cross a process
boundary and must be JSON-normalizable. The candidate process receives input
without labels. The trusted controller retains ground truth and invokes the
scorer after the candidate returns.

Distinguish execution failure from a bad answer:

- Raise an exception for dependency or infrastructure failures that prevented execution. Raise `RetryableCaseError` when a retry may succeed.
- Return `CaseResult(output=...)` when the application ran, even when output is empty or incorrect.
- Do not convert every exception into an error-shaped output object.
- When a harness catches its own rollout errors and hands back a result anyway
  (an agent framework that stores the exception in its state and still
  returns the untouched world), classify that error in `run_case`, before
  constructing the `CaseResult`: a model, provider, or infrastructure failure
  means the case did not run: raise an exception, or `RetryableCaseError` for a transient failure. An agent-side
  failure (a bad tool call, an overlong prompt) is a legitimate zero, so
  include the application error in the JSON `CaseResult.output` and let `score_case`
  put the error in the checks' `message`. `score_case` receives a finished
  `CaseResult` and cannot turn it into a failure, so this decision cannot
  wait until scoring. Check how the harness hands the error back before
  classifying it: it often arrives serialized (a dict or string, not the
  exception), and an `isinstance` check against that is always false, so
  rebuild it with the harness's own helper first or every crash silently
  scores zero. A batch of zeros that finished in milliseconds is a crash, not
  a baseline.

## Prove candidate execution

For repository targets, `run_case` must import and call the candidate's ordinary
application modules. Do not capture production functions at setup time or route
execution to an external deployment that cannot include the candidate edits.
For document targets, consume `runtime.targets_dir` or `runtime.candidate_runtime`
in the real application call. Seed documents must reach that call.

Smoke validates setup, rows, cases, input files and document materialization.
It never invokes `run_case` or `score_case`; setup may contact external services.
A passing smoke check therefore does not establish application quality or hosted
credentials for unexecuted call paths. Use candidate tracing or an explicitly
requested hosted run for execution evidence.
