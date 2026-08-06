# Validation and handoff

## Local validation

Run `beaker run dry-run` after each meaningful integration change, but only after real labeled examples are available. A passing dry-run proves the spec builds and one example executes and scores; a low score is an expected optimization baseline.

Interpret common failures:

- `your runner raised`: inspect application/agent wiring.
- missing or empty split: fix the configured JSONL dataset.
- strict placeholder failure: replace remaining generated TODOs.
- tracing unavailable: install `beaker-sdk[tracing]` before using `--trace`.

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
- Ordinary execution retains application model/client defaults.
- The selected-model branch uses the narrowest injection seam.
- Any LLM judge declares its fixed canonical model with
  `Spec.llm_scorer_model`, independent of `runtime.model`, and uses the hosted
  gateway via `scoring_inference_target()`; deterministic scorers omit the
  field, and direct provider routing is limited to the local dry-run fallback.
- Secrets are confined to `.beaker/.env` or hosted secret storage.
- Local dry-run passes when real data is available.
- Hosted operations occur only after their preconditions and user authorization.

## Final report

Summarize:

- files created or changed;
- selected optimization target;
- dataset and scoring contract;
- how optimized prompts reach the application;
- model-routing behavior;
- local validation command and result;
- exact hosted build/upload/run commands that remain.

When a hosted run is triggered, include the full run UUID and UI link.
