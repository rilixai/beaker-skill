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
7. `tracing_wired`
8. `integration_pushed`
9. `dataset_available`
10. `experiment_launched`

`github_connected` reports only whether the organization's Beaker GitHub App
installation is connected. `agent_selected` requires a selected Beaker agent
with a non-empty repository association that the App can read.
`integration_pushed` confirms that the current checkout's `HEAD` is pushed to
a branch in that selected repository. It is agent-owned: commit and push
without asking the developer to confirm, unless the developer told you not to
take autonomous actions, to a `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch such
as `beaker/20260821-1339-invoice-extraction`, never to `main`, `master`, or the
default branch unless the developer asks. The step's action names the
branch: the current branch when it is already this agent's integration branch
from the last hour, so retries reuse it, and a freshly stamped
`beaker/<YYYYMMDD-HHMM>-<agent-name>` otherwise. When the checkout sits on a
trunk branch, the step reason repeats that branch suggestion. If tracing is
part of the integration, make a best effort to include it in the commit that is
pushed; never commit secret files. Tracing remains optional and advisory and
does not block this step.

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

Interpret the payload with these rules:

- `owner` is `agent` when the coding agent can perform the action and
  `developer` when it requires the human, such as GitHub App access, labeled
  data, agent-name approval, or authorization for a hosted run.
- The next action is the first incomplete agent-owned step in canonical
  order; if no agent-owned step remains, the first known-incomplete
  developer-owned step becomes `next`.
- Developer-owned steps known to be incomplete (`todo`) are listed in
  `blocked_on_developer` in canonical order; relay only newly discovered
  actions verbatim without attempting them, tracking what was already
  reported in this session. This report is not a halt: continue with the
  returned `next.action`.
- An `unknown` step means the check has not completed yet, never that the
  developer must act, and it is not added to `blocked_on_developer`.
- Stop and wait only when `next` itself is developer-owned.
- The `blocking` field is `false` only for advisory `tracing_wired`; it is
  `true` for all other steps. Tracing never blocks completion.
- `integration_pushed` is the final blocking agent-owned step and must be
  complete before a hosted optimization run. It is not required before
  dataset upload. The agent normally completes the later `dataset_available`
  and `experiment_launched` steps too, but the developer may also complete
  them, including through the platform UI.
- Exit code `0` means the state and an actionable `next` were computed, even
  when steps remain incomplete; selection and hosted errors remain in
  `errors` but return `0` when `next` is actionable.
- Exit code `2` is reserved for a not-computed payload where an actionable
  `next` could not be produced, such as an unreadable Beaker config. For exit
  `2`, read `errors`, retry once, and if the failure persists relay the error
  to the developer.
- When onboarding is complete, `next.id` is `null` and `next.action` contains
  the completion message; the null id is an intentional completion shape, not
  a parse failure.

## Smoke validation

`beaker onboarding status` does not import the spec, load its dataset, or
record a smoke result. Run `beaker run smoke --strict` yourself after each
meaningful integration change, but only after real labeled examples are
available.

Choose one dataset source:

```bash
# Offline: validate a real local dataset that remains on disk.
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'

# Remote: validate an immutable hosted revision for the selected agent.
beaker run smoke --strict --agent <selected-agent> --dataset <name@revision>

# Equivalent remote selection by artifact id.
beaker run smoke --strict --agent <selected-agent> --dataset-id <artifact-id>
```

When `config_defaults.dataset_ref` or `config_defaults.dataset_id` already
selects the intended remote snapshot, a bare `beaker run smoke --strict` uses
that selector after resolving the configured agent. Explicit `--dataset` and
`--dataset-id` flags override configured selectors; provide exactly one.

If the installed CLI does not recognize these flags, upgrade `beaker-sdk`
through the repository's existing development-dependency workflow and retry.
Do not bypass the CLI with private API calls.

Local-path smoke is offline. Remote smoke authenticates to Beaker, resolves the
selected snapshot, downloads its standard files through presigned URLs, and
then uses the same local loader to validate every row. It does not start an
optimization run. Prefer immutable `name@revision` or `artifact-id` selectors
over a bare production name, and reuse the exact selector for `beaker run
trigger` so validation and optimization cannot drift to different revisions.

A passing smoke check proves the config resolves, the spec loads, the dataset
loads and parses, and the runner and scorer are connected. The CLI may still
label one structural stage `targets`. It does not execute `run_case`, call the
scorer, make a model/tool call, trigger hosted calls, or report a score.

Interpret common failures:

- `FAIL spec`: use the printed exception type and traceback to fix the factory
  import, construction, or spec contract.
- `FAIL dataset`: use the printed file/line and traceback to fix dataset
  configuration, remote authentication/download, JSONL parsing, or case
  construction.
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
- The `@spec(repository=...)` scope contains the intended application source,
  and `_run_case` imports and executes that source with `targets=None`.
- Repository-mode inputs and `CaseResult.output`/`context` are
  JSON-normalizable, and the spec has no `seed_targets`.
- An intentional `@spec(repository=None)` logical-target spec has real
  `seed_targets` that reach the corresponding model calls.
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
- Credential requirements were derived from every hosted-reachable
  `Spec.run_case` path, including SDK defaults and fallback branches, rather
  than only from existing `spec.required_env` entries.
- `spec.required_env` contains only variables read directly by candidate
  application code. Every declared hosted value is present in encrypted agent
  settings before launch, and any provider routed through Beaker has an
  organization LLM credential. Local shell and `.beaker/.env` values were not
  treated as hosted settings.
- When tracing applies, a best effort was made to wire it so that local
  `beaker run smoke --strict` passes with no tracing warning before the
  integration is committed and pushed; an unresolved tracing warning never
  blocks the push. If tracing detection is `UNKNOWN`, report that verification
  uncertainty rather than treating it as a tracing failure; it does not block
  the push.
- The completed integration is committed and pushed by the agent, without
  asking the developer unless the developer disallowed autonomous actions, to a
  `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch in
  the selected agent repository; secrets are not staged.
- Hosted operations occur only after their preconditions and user authorization.

## Final report

Summarize:

- files created or changed;
- selected optimization target;
- dataset and scoring contract;
- the repository optimization scope and how `_run_case` reaches candidate
  application code;
- model-routing behavior;
- structural validation command and result, plus any separately captured
  runtime evidence;
- exact hosted upload/run commands that remain.

When a hosted run is triggered, include the full run UUID and UI link.
