# Dataset and spec wiring

## Establish the dataset contract

Find real labeled examples in local evals, tests, JSONL/CSV files, API fixtures, or uploaded datasets. For the selected task, identify:

- input shape;
- expected/ground-truth shape;
- prediction fields;
- scoring rules and field weights;
- train and validation examples;
- stable row identifiers and optional grouping/metadata.

Declare the matching JSON Schema through the loader/spec so uploads can be validated. A `Case` is one evaluation example: input plus expected values. Do not infer labels, conventions, edge cases, or split composition from application code or prose.

If local data is unavailable, inspect hosted data with `beaker dataset list` and `beaker dataset show`. If neither source has usable labels, direct the developer to upload or provide real examples and stop before finalizing the spec, running dry-run, building, or uploading synthetic data.

## Map repository code into the spec

| Spec component | Repository source of truth |
|---|---|
| `_seed_targets` | Current system prompts, templates, or prompt constants |
| `_run_case` | Real async agent/LLM evaluation path; thread every target prompt into its call sites |
| scorer | Prediction and ground-truth fields plus objective weights |
| data loader | Real labeled rows and their validation contract |

Keep `score_case` async because Beaker awaits it, even for deterministic scoring. Use `objective_score(..., field_weights=...)` when fields have different importance.

Distinguish execution failure from a bad answer:

- Return `CaseResult.failed(error, retryable=...)` for harness, dependency, or infrastructure failures that prevented execution.
- Return `CaseResult(output=...)` when the application ran, even when output is empty or incorrect.
- Do not convert every exception into an error-shaped output object.

## Prove prompt application

For every `_seed_targets` entry, trace the path into the real model call. Rebuild or clone constructor-bound agents per target bundle, or add a narrow `apply_targets`/factory seam. Add a captured-call assertion, test double, or smoke test that fails if the target prompt is ignored.

Do not place uploaded data under `.beaker/`; that directory owns Beaker configuration, credentials, and local trace receipts.
