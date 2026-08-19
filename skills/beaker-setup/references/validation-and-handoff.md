# Validation and handoff

## Onboarding status

Use `beaker onboarding status` after every CLI command and whenever the next
action is unclear. It reports these ordered steps:

1. `beaker_dependency_declared`
2. `config_present`
3. `logged_in`
4. `github_connected`
5. `agent_selected`
6. `spec_integrated`
7. `spec_validated`
8. `tracing_wired`
9. `dataset_available`
10. `experiment_launched`

`github_connected` reports only whether the organization's Beaker GitHub App
installation is connected. `agent_selected` requires a selected Beaker agent
with a non-empty repository association that the App can read.

Onboarding is complete once `experiment_launched` is complete. Shipping a
winning candidate pull request is developer-owned follow-up work outside the
onboarding loop.

The human-readable output identifies each step as `PASS`, `TODO`, `UNKNOWN`, or
`ADVISORY`, then prints one `Next:` action. `--json` returns:

```json
{
  "steps": [
    {
      "id": "config_present",
      "state": "complete",
      "reason": null,
      "owner": "agent",
      "next_action": "...",
      "blocking": true
    }
  ],
  "next": {
    "id": "logged_in",
    "owner": "agent",
    "action": "Run `beaker login`."
  },
  "blocked_on_developer": [
    {
      "id": "github_connected",
      "action": "Ask the developer to install the Beaker GitHub App for the organization."
    }
  ],
  "errors": []
}
```

`owner` is `agent` when the coding agent can perform the action and
`developer` when it requires the human, such as GitHub App access, labeled
data, agent-name approval, or authorization for a hosted run. The next action
is the first incomplete agent-owned step in canonical order. Developer-owned
steps known to be incomplete (`todo`) are listed in `blocked_on_developer` in
canonical order; relay those actions verbatim and stop rather than attempting
them. An `unknown` step means the check has not completed yet, never that the
developer must act, and it is not added to `blocked_on_developer`. If no
agent-owned step remains, the first known-incomplete developer-owned step
becomes `next`. The `blocking` field is `false` only for advisory
`tracing_wired`; it is `true` for all other steps. Tracing never blocks
completion, but is returned as the final agent action once no other
agent-owned step remains. Exit code `0` means the state and an actionable
`next` were computed, even when steps remain incomplete. Exit code `2` is
reserved for a not-computed payload where an actionable `next` could not be
produced, such as an unreadable Beaker config; selection and hosted errors
remain in `errors` but return `0` when `next` is actionable.
When onboarding is complete, `next.id` is `null` and `next.action` contains
the completion message; the null id is an intentional completion shape, not a
parse failure. For exit `2`, read `errors`, retry once, and if the failure
persists relay the error to the developer.

## Local validation

Run `beaker run smoke --strict` after each meaningful integration change, but
only after real labeled examples are available. The `spec_validated` onboarding
step performs this same local structural/readiness check only after
`spec_integrated` is complete. It reports failures in the step reason and
points back to `beaker run smoke --strict`; it does not print smoke output or
write files. A passing smoke check proves the config resolves, the spec builds,
the dataset loads and parses, and the targets, runner, and scorer are
connected. It does not execute `run_case`, call the scorer, make a model/tool
call, trigger hosted calls, or report a score.

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
  its output shows no tracing warning after the final `tracing_wired` action
  has been completed. If tracing detection is `UNKNOWN`, report that
  verification uncertainty rather than treating it as a tracing failure.
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
