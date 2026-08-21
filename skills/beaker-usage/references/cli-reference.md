# Beaker usage CLI reference

## Contents

- [Global command placement](#global-command-placement)
- [Onboarding status](#onboarding-status)
- [Discovery](#discovery)
- [Launch commands](#launch-commands)
- [Selected-model flags](#selected-model-flags)
- [Run lifecycle](#run-lifecycle)
- [Status exit codes](#status-exit-codes)
- [Common failures](#common-failures)

## Global command placement

Run from the configured Beaker project root. Put global selectors before the
command group:

```bash
beaker --config-file services/invoices/.beaker/beaker.yaml run list --json
```

Select an agent before a dataset or run command. State which agent you selected,
then pass it with `--agent` so every command uses the same one.

## Onboarding status

```bash
beaker onboarding status
beaker onboarding status --json
```

Use this command during setup validation and launch preparation, after each
CLI command and whenever the next action is unclear. For inspecting,
monitoring, pulling, or cancelling a known run with its preconditions met,
run only the relevant command and consult onboarding status only after a
failure or when the next action is unclear.

Steps and completion:

- The ordered steps are `beaker_dependency_declared`, `config_present`,
  `logged_in`, `github_connected`, `agent_selected`, `spec_integrated`,
  `spec_validated`, `tracing_wired`, `integration_pushed`,
  `dataset_available`, and `experiment_launched`.
- Onboarding is complete once `experiment_launched` is complete. Shipping a
  winning candidate pull request is developer-owned follow-up work outside
  the onboarding loop.
- `github_connected` checks only the organization's GitHub App installation;
  `agent_selected` also requires a selected agent with a non-empty repository
  association that the App can read.
- `tracing_wired` has `blocking: false`, so it is optional and advisory: when
  tracing is included, make a best effort to complete its wiring as part of
  the integration before pushing, but never let it delay the required push.
- `integration_pushed` is the final blocking agent-owned step; it must be
  complete before a hosted optimization run, but is not mandatory for dataset
  upload. The agent normally completes the later `dataset_available` and
  `experiment_launched` steps too, but the developer may also complete them,
  including through the platform UI.

Reading the JSON and acting on it:

- JSON contains `steps`, `next`, `blocked_on_developer`, and `errors`; each
  step has `id`, `state`, `reason`, `owner`, `next_action`, and `blocking`;
  `next` has `id`, `owner`, and `action`; and `blocked_on_developer` lists
  developer-owned known-incomplete (`todo`) steps with their relayable
  actions.
- `next` is the first incomplete agent-owned step in canonical order. If no
  agent-owned step remains, `next` is the first known-incomplete
  developer-owned step. Follow the returned action.
- Relay only newly discovered blocked developer actions verbatim without
  attempting them, tracking what was already reported in this session, then
  continue with the returned `next.action`.
- An `unknown` step has not been checked yet and never means the developer
  must act, so it is not listed in `blocked_on_developer`.
- Stop and wait only when `next` itself is developer-owned.
- When onboarding is complete, `next.id` is `null` and `next.action` contains
  the completion message.
- Exit `0` means the state and an actionable `next` were computed, even if
  incomplete; selection and hosted errors remain in `errors` but return `0`
  when `next` is actionable.
- Exit `2` is reserved for a not-computed payload where no actionable `next`
  could be produced. For exit `2`, read `errors`, retry once, and if the
  failure persists relay the error to the developer.

## Discovery

```bash
beaker auth status
beaker agent list
beaker github status --repo <owner/repository>
beaker github branches --repo <owner/repository> --json
beaker dataset list --agent <selected-agent> --json
beaker dataset show <dataset-name-or-revision> --agent <selected-agent> --json
beaker model list --available-only --json
```

`github branches` uses the stored user CLI login. Run `beaker login` only when
that login is missing or expired. Runtime commands use the project credentials
created during setup.

## Launch commands

Without `--ref`, the CLI uses the current checked-out branch when it belongs to
the linked repository and exists on its remote. Otherwise, it uses the
repository's GitHub default branch. The command prints the current branch when
selected locally, or `default branch` when the server selects the fallback.
Pass `--ref <remote-branch>` only to override this selection with another
remote branch, preferably one returned by `beaker github branches`.

Default optimization over the configured editable surface:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> --json
```

Repository mode uses `@spec()` or `@spec(repository=...)`, has no
`seed_targets`, passes `targets=None`, and TEST-evaluates only the selected
winner. Named-resource mode uses `@spec(repository=None)` and supplies each
complete named resource through `Spec.seed_targets`. For named-resource
default optimization, `--test-all-candidates` evaluates every persisted
candidate on TEST; without it, only the selected winner is TEST-evaluated.
Repository-surface default optimization always evaluates only the winner on TEST
and ignores the flag.
The seed starts with the configured production-system model behavior, but
optimization may change model selection or model-call behavior within the editable
surface when that improves the objective.

Production-system optimize-only:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --execution-mode optimize_only --json
```

Selected-model benchmark and optimization for a spec with populated
`seed_targets`. The split values below are illustrative, not defaults; use the
benchmark defaults unless the developer chooses splits:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --optimization-model openai:<model-a> \
  --optimization-model anthropic:<model-b> \
  --execution-mode benchmark_and_optimize \
  --benchmark-split TEST \
  --benchmark-max-cases 30 \
  --final-eval-split VAL \
  --json
```

`--ref` overrides the automatic selection with a remote GitHub branch. It does
not push or include local-only commits or working tree changes. Tags and commit
SHAs are not valid hosted sources; the server returns `422` with
`<owner/repository>@<ref> is not a GitHub branch.` Ask for a remote branch that
points to the intended commit instead.

## Launch config overrides with `--config`

`beaker run trigger --config '<json>'` takes a JSON object of launch-config
overrides. `config_defaults` in `.beaker/beaker.yaml` form the base and
`--config` overrides them; the merged object must satisfy the strict server
launch contract, which rejects unknown keys with `422`. Do not confuse this
flag with the global `--config-file` option, which selects the YAML file.

Prefer typed flags whenever one exists. Use `--config` only for launch keys
that have no typed flag, when the developer explicitly asks for them:
`spend_budget_usd`, `prompts_to_update`, `top_k_test_eval`, `test_baseline`,
and `extra` (opaque passthrough to the spec factory via
`OptimizationContext.config`). Never
hand-author `optimization_config` inside `--config`: typed model flags and
`--execution-mode optimize_only` both reject it, and plain runs should let the
platform choose.

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --config '{"spend_budget_usd": 5}' --json
```

## Selected-model flags

| Flag | Contract |
|---|---|
| `--optimization-model provider:model` | Repeat 1–8 times; values must come from `model list` |
| `--execution-mode` | `optimize_only` for the production system with no model flags, or `benchmark_and_optimize` for selected models; selected-model default is `benchmark_and_optimize` |
| `--benchmark-split` | `VAL` or `TEST` |
| `--benchmark-max-cases` | 1–1000 |
| `--final-eval-split` | Repeatable `VAL` or `TEST` |
| `--test-all-candidates` | Evaluate every persisted candidate on `TEST` for named-resource default optimization (`repository=None`), including resources such as `wiki`; repository-surface default optimization and selected-model runs ignore the flag and always test only the winner |

Do not combine selected-model flags with `--use-harness-optimization` or with
an `optimization_config` supplied through `--config`. Do not combine
`--optimization-model` with `--execution-mode optimize_only`; optimize-only
uses the production system. Selected-model runs require an explicit
spec with populated `seed_targets`; do not infer compatibility from the
`repository` setting. The CLI does not expose a benchmark-only mode.

## Run lifecycle

```bash
# Discover runs.
beaker run list --json
beaker run list --status RUNNING --limit 25 --offset 0 --json

# Check once.
beaker run status <run-id> --json

# Poll for at most 45 seconds.
beaker run status <run-id> --watch --poll-interval 15 --poll-timeout 45 --json

# Cancel atomically.
beaker run cancel <run-id> --json

# Download candidates and evaluation reports.
beaker run pull <run-id> --output-dir .beaker/results/<run-id>
```

Run-list filters include `--status`, `--trigger-reason`, `--limit` from 1
through 100, and non-negative `--offset`.

## Status exit codes

| Code | Meaning | Agent action |
|---|---|---|
| `0` | Run completed | Report completion; pull results if requested |
| `1` | Run is terminal but failed or was cancelled | Report status and `error_message` when present |
| `2` | Client, authorization, validation, or lookup error | Diagnose the printed error; do not label the run failed without a run response |
| `3` | Run is still active, or a bounded poll timed out | Continue monitoring only if requested |

JSON polling emits one document: the final response observed during that
invocation. A timeout message may also appear on stderr with exit code `3`.

## Common failures

- **Command or flag is missing:** the installed Beaker CLI predates the usage
  lifecycle. Report that it must be upgraded through the repository's existing
  dependency workflow; do not call the API directly.
- **Not logged in:** run `beaker login`, then retry GitHub branch discovery.
- **Repository is unreadable:** ask the developer or organization owner to
  update the GitHub App installation. Use `$beaker-setup` for connection work.
- **Source is not a GitHub branch (`422`):** the supplied `--ref` is a tag,
  commit SHA, or unknown branch. Select a remote branch returned by `beaker
  github branches`; do not retry with the tag or SHA.
- **No datasets:** stop and use `$beaker-setup`; do not invent or upload
  synthetic optimization data.
- **Missing required evaluation environment variables:** the run fails before
  candidate dispatch. Use `$beaker-setup` to set each declared name with
  `beaker agent env set NAME --value-stdin`, then start a new run.
- **Selected-model optimizer requires `Spec.seed_targets`:** selected-model
  flags were used with a spec that has no targets. Stop and use
  `$beaker-setup`; do not mutate the spec as a run-management side effect.
- **No available models:** selected-model execution is not ready. Ask the
  developer to configure provider credentials or choose optimization.
- **Unsupported or unavailable model:** rerun
  `beaker model list --available-only --json` and ask the developer to choose
  from that result.
- **Run remains `PREPARING_BUILD` or `QUEUED`:** report the state and do not
  retrigger.
- **Run is `FAILED`:** report `error_message` and the UI link. Do not edit the
  integration unless the developer asks to diagnose or repair it.
- **Cancellation rejects a terminal run:** report the authoritative terminal
  state; do not retry cancellation in a loop.
