# Dataset and spec wiring

## Establish the dataset contract

Find real labeled examples in local evals, tests, JSONL/CSV files, API fixtures,
or uploaded datasets. Treat existing tests and fixtures as read-only evidence;
never edit or repurpose them for Beaker. For the selected task, identify:

- input shape;
- expected/ground-truth shape;
- prediction fields;
- scoring rules and field weights;
- train and validation examples;
- stable row identifiers and optional grouping/metadata.

Declare the matching JSON Schema through the loader/spec so uploads can be validated. A `Case` is one evaluation example: input plus expected values. Do not infer labels, conventions, edge cases, or split composition from application code or prose.

If local data is unavailable, inspect hosted data with `beaker dataset list` and `beaker dataset show`. If neither source has usable labels, direct the developer to upload or provide real examples and stop before finalizing the spec, running smoke validation, or uploading synthetic data.

## Convert without persisting generated datasets

When real labeled source data must be converted to Beaker's JSONL layout, keep
the conversion script under `.beaker/` and write its generated splits only to an
OS-managed temporary directory. Run validation, when needed, and the CLI upload
synchronously inside the temporary-directory context so cleanup happens after
the CLI has finished reading the files. Never write generated JSONL into the
repository, `.beaker/`, an existing fixture directory, or another persistent
output directory.

Use `tempfile.TemporaryDirectory()` instead of an open `NamedTemporaryFile`, so
the Beaker subprocess can reopen the files reliably across platforms:

```python
import json
import subprocess
import tempfile
from pathlib import Path


with tempfile.TemporaryDirectory(prefix="beaker-dataset-") as temp_dir:
    dataset_dir = Path(temp_dir)
    splits = {"train": train_rows, "val": val_rows}

    for split_name, rows in splits.items():
        split_path = dataset_dir / f"{split_name}.jsonl"
        with split_path.open("w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row) + "\n")

    subprocess.run(
        [
            "beaker", "dataset", "upload", str(dataset_dir),
            "--name", dataset_name,
            "--total-count", str(sum(len(rows) for rows in splits.values())),
            "--split", f"train={len(train_rows)}",
            "--split", f"val={len(val_rows)}",
            "--agent", agent_key,
        ],
        check=True,
    )
```

The CLI currently requires a dataset directory or JSONL file path; this staging
is temporary filesystem materialization, not a repository artifact. Do not add
generated dataset paths to `.gitignore` as a substitute for temporary storage.

## Map repository code into the spec

Keep the spec and its helper adapters under `.beaker/`. Import the application's
public or existing internal interfaces from the spec; do not create Beaker
orchestration modules in the application package. Never create or modify test
files, fixtures, snapshots, helpers, or test configuration for Beaker.

| Spec component | Repository source of truth |
|---|---|
| `@spec(repository=...)` | Eligible ordinary source files Beaker may improve; omitted means `"all"` |
| `_run_case` | Real async application evaluation path; repository mode receives `targets=None` |
| scorer | Prediction and ground-truth fields plus objective weights; it remains immutable under `.beaker/` |
| `llm_scorer_model` | Optional fixed canonical `provider:model` for an LLM judge; omit for deterministic scoring |
| data loader | Real labeled rows and their validation contract |
| `spec.required_env` | Names of application variables needed during candidate evaluation; never their values |

Keep `score_case` async because Beaker awaits it, even for deterministic scoring. Use `objective_score(..., field_weights=...)` when fields have different importance.

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
add tests or test doubles.

The default `@spec()` scope is all eligible ordinary UTF-8 source. Use
`repository=("path", ...)` when the developer wants a smaller source-relative
surface. Hidden paths, `.beaker`, dependency manifests, lock files, build
configuration, vendored source, and binary files are protected. Repository
mode has no `seed_targets`, passes `targets=None`, and reserves TEST evaluation
for the selected winner.

For a logical-target spec, preserve explicit `@spec(repository=None)`. That mode
requires real `Spec.seed_targets`; inspect each prompt or named resource path into
the application exactly as before. Selected-model runs require this logical
target contract and are not valid for the default
repository-only spec.

Do not place datasets under `.beaker/`. Existing labeled data is source material,
not Beaker-owned tooling: leave it in its established location and reference it
from the config or command. Generated JSONL conversions exist only in an
OS-managed temporary directory for validation/upload. `.beaker/` owns Beaker
config, specs, adapters, conversion scripts, credentials, and local trace
receipts, but not generated dataset outputs.
