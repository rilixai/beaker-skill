# Validation and handoff

## Local validation

Run `beaker run smoke --strict` after each meaningful integration change, but
only after real labeled examples are available. A passing smoke check proves the
config resolves, the spec builds, the dataset loads and parses, and the targets,
runner, and scorer are connected. It does not execute `run_case`, call the
scorer, make a model/tool call, or report a score.

Interpret common failures:

- `FAIL spec`: use the printed exception type and traceback to fix the factory
  import, construction, or spec contract.
- `FAIL dataset`: use the printed file/line and traceback to fix dataset
  configuration, JSONL parsing, or case construction.
- missing or empty split: add real examples to the requested split or select
  the correct split.
- missing runner/scorer callable: connect the required spec hook.
- strict placeholder failure: replace remaining generated TODOs.
- tracing warning: smoke warns, without changing its exit code (even with
  `--strict`), when no framework adapter or `runtime.trace.model_call` is
  wired in application code. Captures would record no model I/O. Wire tracing
  as described in
  [model-routing-and-tracing.md](model-routing-and-tracing.md) — `beaker trace
  instrument` detects the framework and installs its extras — then re-run
  smoke until the warning is gone.

The command prints each completed stage as `PASS` before a later failure, so use
the last passing stage to narrow the problem. For runtime evidence, exercise
the candidate workflow rooted at the main workflow agent inside `Spec.run_case`,
including its sub-agents, tools, retrievers, and nested model calls, under a
local Beaker capture. Then run `beaker trace doctor --require-model-calls` and
inspect the receipt with `beaker trace inspect .beaker/traces`. A capture
containing only scorer or judge calls does not satisfy runtime trace validation.
Run `beaker trace instrument --check` first when instrumentation is uncertain;
smoke does not support `--trace`.

Synthetic rows are allowed only when the developer explicitly requests a smoke-only wiring check. Label them clearly, never upload them as optimization data, and never present them as validation of the real contract.

## Completion checklist

- Beaker-owned config, specs, adapters, credentials, and traces are under
  the selected project's `.beaker/` directory.
- No tests, fixtures, snapshots, test helpers, or test configuration were
  created or modified; existing tests were read-only evidence.
- Production entrypoints and deployment/runtime configuration do not import,
  initialize, or route through Beaker.
- Any application-code edit is a minimal optional injection seam with unchanged
  defaults and no Beaker import; otherwise application code is untouched.
- Beaker is recorded as development/tooling rather than a production runtime
  dependency when the project supports that separation.
- The selected task is explicit.
- Input, ground truth, prediction, and scoring contracts come from real data.
- Every optimized prompt reaches its corresponding model call.
- Runtime trace evidence comes from the candidate workflow rooted at the main
  workflow agent inside `Spec.run_case`, including its sub-agents, tools,
  retrievers, and nested model calls, and excludes scorer, judge, evaluator,
  post-processing, and post-rollout model calls.
- Ordinary execution retains application model/client defaults.
- The selected-model branch uses the narrowest injection seam.
- Any LLM judge declares its fixed canonical model with
  `Spec.llm_scorer_model`, independent of `runtime.model`, and uses the hosted
  gateway via `scoring_inference_target()`; deterministic scorers omit the
  field, and direct provider routing is limited to the local application/evaluation fallback.
- Secrets are confined to `.beaker/.env` or hosted secret storage.
- Local `beaker run smoke --strict` passes when real data is available, and
  its output shows no tracing warning.
- Hosted operations occur only after their preconditions and user authorization.

## Final report

Summarize:

- files created or changed;
- selected optimization target;
- dataset and scoring contract;
- how optimized prompts reach the application;
- model-routing behavior;
- structural validation command and result, plus any separately captured
  runtime evidence;
- exact hosted build/upload/run commands that remain.

When a hosted run is triggered, include the full run UUID and UI link.
