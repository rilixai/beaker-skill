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
failure or when the next action is unclear. It reports the ordered steps
`beaker_dependency_declared`,
`config_present`, `logged_in`, `github_connected`, `agent_selected`,
`spec_integrated`, `spec_validated`, `tracing_wired`, `dataset_available`, and
`experiment_launched`. Onboarding is
complete once `experiment_launched` is complete. Shipping a winning candidate
pull request is developer-owned follow-up work outside the onboarding loop.
`github_connected` checks only the organization's GitHub App installation;
`agent_selected` also requires a selected agent with a non-empty repository
association that the App can read.
JSON contains `steps`, `next`, `blocked_on_developer`, and `errors`; each step
has `id`, `state`, `reason`, `owner`, `next_action`, and `blocking`; `next` has
`id`, `owner`, and `action`; and `blocked_on_developer` lists developer-owned
known-incomplete (`todo`) steps with their relayable actions. `next` is the
first incomplete agent-owned step in canonical order. Relay every blocked
developer action verbatim and stop rather than attempting it; an `unknown`
step has not been checked yet and never means the developer must act, so it is
not listed in `blocked_on_developer`. If no agent-owned step remains, `next` is
the first known-incomplete developer-owned step. Exit `0` means the state and
an actionable `next` were computed, even if incomplete; exit `2` is reserved
for a not-computed payload where no actionable `next` could be produced.
Selection and hosted errors remain in `errors` but return `0` when `next` is
actionable.
`tracing_wired` has `blocking: false` and is returned as the final agent action
once no other agent-owned step remains. Follow the returned action, and relay
developer-owned actions verbatim.
When onboarding is complete, `next.id` is `null` and `next.action` contains
the completion message. For exit `2`, read `errors`, retry once, and if the
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
Pass `--ref` only to override this selection.

Optimization:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> --json
```

Harness Optimization:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --use-harness-optimization --json
```

Production-system optimize-only:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --execution-mode optimize_only --json
```

Selected-model benchmark and optimization:

```bash
beaker run trigger --agent <selected-agent> --dataset <name@revision> \
  --optimization-model openai:<model-a> \
  --optimization-model anthropic:<model-b> \
  --execution-mode benchmark_and_optimize \
  --benchmark-split TEST \
  --benchmark-max-cases 30 \
  --final-eval-split VAL \
  --test-all-candidates \
  --json
```

`--ref` overrides the automatic branch selection with a remote GitHub ref. It
does not push or include local-only commits or working tree changes.

## Selected-model flags

| Flag | Contract |
|---|---|
| `--optimization-model provider:model` | Repeat 1–8 times; values must come from `model list` |
| `--execution-mode` | `optimize_only` for the production system with no model flags, or `benchmark_and_optimize` for selected models; selected-model default is `benchmark_and_optimize` |
| `--benchmark-split` | `VAL` or `TEST` |
| `--benchmark-max-cases` | 1–1000 |
| `--final-eval-split` | Repeatable `VAL` or `TEST` |
| `--test-all-candidates` | Evaluate every persisted candidate on `TEST`; otherwise only the selected best candidate is test-evaluated |

Do not combine selected-model flags with `--use-harness-optimization` or with
an `optimization_config` supplied through `--config`. Do not combine
`--optimization-model` with `--execution-mode optimize_only`; optimize-only
uses the production system. The CLI does not expose a benchmark-only mode.

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

Run-list filters include `--scope-key`, `--status`, `--trigger-reason`,
`--limit` from 1 through 100, and non-negative `--offset`.

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
- **No datasets:** stop and use `$beaker-setup`; do not invent or upload
  synthetic optimization data.
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
