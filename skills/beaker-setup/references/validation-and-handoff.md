# Validation and handoff

## Onboarding status

Use `beaker onboarding status` after a completed onboarding step — `beaker init`,
the dependency install, a meaningful integration edit, `beaker agent setup`, the push,
dataset selection, smoke, or trigger — and whenever the next action is unclear.
Do not run it after `--help`, `--print`, a discovery-only `beaker agent list`, or
other read-only probes unless you are stuck. It reports these ordered steps:

1. `beaker_dependency_declared`
2. `config_present`
3. `logged_in`
4. `github_connected`
5. `agent_selected`
6. `integration_configured`
7. `tracing_wired`
8. `dataset_available`
9. `required_env_configured`
10. `integration_pushed`
11. `experiment_launched`

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

Before marking this step complete, inspect `git status --short`, stage the exact files
intentionally created or changed for the integration, and review `git diff
--cached --name-only`. The status check detects tracked changes under the
selected source tree and known new integration files such as the selected
config, integration target, dependency metadata, lockfiles, and `.beaker/.gitignore`.
It intentionally ignores other untracked files under `source_dir`, because
existing datasets and unrelated working files are not automatically part of a
Beaker integration. The status result does not decide what belongs in the
commit. Never stage an unrelated dataset or source file merely to make the
step pass, and ensure every intentional new integration file is staged.

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
  reported in this session. Continue with the returned `next.action` while
  independent agent work remains. Do not perform `integration_pushed` while
  `dataset_available` or `required_env_configured` is incomplete; wait once no
  earlier agent work remains.
- An `unknown` step means the check has not completed yet, never that the
  developer must act, and it is not added to `blocked_on_developer`.
- Stop and wait only when `next` itself is developer-owned.
- The `blocking` field is `false` only for advisory `tracing_wired`; it is
  `true` for all other steps. Tracing never blocks completion.
- `integration_pushed` is the final blocking agent-owned step and must be
  complete before a hosted optimization run. It is not required before
  dataset upload. Complete `dataset_available` and `required_env_configured`
  first so the selected config, dataset, and dependency files need one final
  integration push. The agent normally completes dataset selection and
  `experiment_launched` too, but the developer may also complete them through
  the platform UI.
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

`beaker onboarding status` does not import the integration, load its dataset, or
record a smoke result. Run `beaker run smoke --strict` yourself after each
meaningful integration change, but only after real labeled examples are
available.

Choose one dataset source:

```bash
# Local dataset: setup hooks may still perform external I/O.
beaker run smoke --strict --integration-id <id> --config '{"local_dataset_path":"<dataset-dir>"}'

# Remote: validate an immutable hosted revision for the selected agent.
beaker run smoke --strict --integration-id <id> --agent <selected-agent> --dataset <name@revision>

# Equivalent remote selection by artifact id.
beaker run smoke --strict --integration-id <id> --agent <selected-agent> --dataset-id <artifact-id>
```

During onboarding, retain the immutable remote selector and pass it explicitly
to smoke and the later trigger; do not commit an organization-specific selector
to YAML by default. When a repository intentionally defines
`config_defaults.dataset_ref` or `config_defaults.dataset_id`, `beaker run smoke
--strict --integration-id <id>` uses that dataset selector after resolving the
configured agent.
Explicit `--dataset` and `--dataset-id` flags override configured selectors;
provide exactly one.

If the installed CLI does not recognize these flags, upgrade `beaker-sdk`
through the repository's existing development-dependency workflow and retry.
Do not bypass the CLI with private API calls.

Local-path smoke reads local rows; customer setup hooks may still perform external I/O. Remote smoke authenticates to Beaker, resolves the
selected snapshot, downloads its standard files through presigned URLs, and
then uses the same local loader to validate every row. It does not start an
optimization run. Prefer immutable `name@revision` or `artifact-id` selectors
over a bare production name, and reuse the exact selector for `beaker run
trigger` so validation and optimization cannot drift to different revisions.

A passing smoke check proves the config resolves, the Integration contract
validates, typed rows load, and setup produces valid cases and files. For
documents, it also validates/materializes the seed and enters/closes one
candidate context. Smoke closes setup resources and never calls `run_case`
or `score_case`. Setup hooks can perform external I/O; smoke does not report
application quality or start a hosted optimization run.

Interpret common failures:

- `FAIL integration`: use the printed exception type and traceback to fix the module
  import, exported Integration value, or contract.
- `FAIL dataset`: use the printed file/line and traceback to fix dataset
  configuration, remote authentication/download, JSONL parsing, or row
  validation.
- `FAIL setup`: fix the setup context, case loader, case files, duplicate IDs,
  seed documents, or candidate context named in the traceback.
- missing or empty split: add real examples to the requested split or select
  the correct split.
- missing runner/scorer callable: connect the required integration hook.
- strict placeholder failure: replace remaining generated TODOs.
- tracing warning: smoke warns, without changing its exit code (even with
  `--strict`), when no framework integration or `runtime.trace.model_call` is
  wired in application code. Captures would record no model I/O. Wire tracing
  as described in
  [model-routing-and-tracing.md](model-routing-and-tracing.md) — `beaker trace
  instrument` detects the framework and installs its extras — then re-run
  smoke until the warning is gone.

The command prints each completed stage as `PASS` before a later failure, so use
the last passing stage to narrow the problem. For runtime evidence, exercise
the candidate workflow rooted at the main workflow agent inside `Integration.run_case`,
including its sub-agents, tools, retrievers, and nested model calls, under a
local Beaker capture. Then run `beaker trace doctor --require-model-calls` and
inspect the receipt with `beaker trace inspect .beaker/traces`. A capture
containing only scorer or judge calls does not satisfy runtime trace validation.
Run `beaker trace instrument --check` first when instrumentation is uncertain;
smoke does not support `--trace`.

Synthetic rows are allowed only when the developer explicitly requests a smoke-only wiring check. Label them clearly, never upload them as optimization data, and never present them as validation of the real contract.

## Completion checklist

- Beaker-owned config, integrations, helper code, credentials, and traces are under
  the selected project's `.beaker/` directory.
- No tests, fixtures, snapshots, test helpers, or test configuration were
  created or modified, and the repository's test suite was not run; existing
  tests were read-only evidence.
- No CI/CD automation was created or modified: no workflow or pipeline job, no
  pre-commit hook, and no `Makefile`, task-runner, or script entry that runs
  Beaker.
- Production entrypoints and deployment/runtime configuration do not import,
  initialize, or route through Beaker.
- Any application-code edit is a minimal optional injection seam with unchanged
  defaults and no Beaker import; otherwise application code is untouched.
- Beaker is recorded as development/tooling rather than a production runtime
  dependency when the project supports that separation.
- `integrations.<id>.source_dir` resolves from the Git checkout root, and
  `integrations.<id>.package_import_root` resolves to an existing directory inside it in the
  pushed commit.
- The evaluator's dependencies come from the pushed bundle's `pyproject.toml`
  or from `integrations.<id>.pip_install`/`integrations.<id>.apt_install`, not from the local
  environment.
- The selected task is explicit.
- Input, ground truth, prediction, and scoring contracts come from real data.
- `repository(...)` contains the intended application source and `run_case`
  imports and executes that candidate source.
- Case inputs, expected values and application results are JSON values.
  Scorer-required application state is part of `CaseResult.output`; model/tool
  telemetry is captured through `runtime.trace`.
- A document Integration returns real seed documents and consumes the candidate
  through `runtime.targets_dir` or `runtime.candidate_runtime`.
- Runtime trace evidence comes from the candidate workflow rooted at the main
  workflow agent inside `Integration.run_case`, including its sub-agents, tools,
  retrievers, and nested model calls, and excludes scorer, judge, evaluator,
  post-processing, and post-rollout model calls.
- Ordinary execution retains application model/client defaults.
- Tracing and model injection preserve the client type: no transparent Python proxy,
  `__getattr__` forwarder, or monkeypatched object stands in for a client the
  application or harness checks. The only exception is a framework-specific,
  type-preserving adapter that subclasses the public client base the framework
  validates and passes the application's resolver or type check before the
  hosted baseline. Where that is not possible, the plain client is kept and the
  tracing gap is reported.
- When `runtime.model` is set, use the narrowest injection seam and verify the
  actual requested model. Automatic proxy routing does not select it.
- Initial routing prefers automatic platform access, then a compatible explicit
  gateway when the setup cannot use automatic routing. Customer clients and
  credentials are the last resort or an explicit developer choice. Unsupported
  calls, SDK limits, and required customer credentials are named at handoff;
  existing hosted billing choices are preserved. The optional model/client
  override is wired when a narrow injection seam exists; comparison support is
  checked separately from routing success.
- Any LLM judge's approved fixed canonical `scorer_model` is present in the
  actual launch configuration, independent of `runtime.model`, and it uses the
  hosted gateway via `scoring_inference_target()`. A missing model raises during
  hosted scoring and is not checked by smoke. Deterministic scorers omit the
  field and do not call the helper. A judge call recorded by the automatic proxy
  is not dedicated scorer accounting; direct judge clients remain the local
  application/evaluation fallback.
- Credential requirements were derived from every hosted-reachable setup,
  case-loading, document-initialization, application and scoring path, including
  SDK defaults and fallback branches, not from existing
  `integrations.<id>.required_env` entries alone.
- `integrations.<id>.required_env` contains the variables those paths read directly,
  including setup-only credentials. Required secrets are available from hosted
  settings. Readable organization provider keys fill declared canonical variables
  when no agent value is set and keep direct provider billing. Missing canonical
  keys can instead be covered by confirmed hosted proxy routing for supported
  calls, using platform credentials without an organization-key lookup. No real
  provider key was created or waited on solely for such routing or explicit
  gateway access. Local shell and `.beaker/.env` values were not treated as hosted
  settings.
- Every Beaker YAML or agent-setting correction was followed by a new run;
  existing runs were not expected to pick up later changes.
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

Summarize in plain English:

- files created or changed;
- selected optimization target;
- dataset and scoring contract;
- the repository optimization scope and how `run_case` reaches candidate
  application code;
- model-routing behavior;
- structural validation command and result, plus any separately captured
  runtime evidence;
- exact hosted upload/run commands that remain.

When a hosted run is triggered, immediately tell the developer that repository
setup is finished, include the full run UUID, UI link, and current state, and
make clear that any remaining wait is for Beaker's hosted run rather than more
integration work. If monitoring continues, report meaningful state changes
without implying that setup is still in progress.
