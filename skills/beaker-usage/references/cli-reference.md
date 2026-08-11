# Beaker usage CLI reference

## Contents

- [Global command placement](#global-command-placement)
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

Agent selection precedence is explicit `--agent`, then `BEAKER_AGENT_KEY`, then
the selected Beaker config. Usually omit `--agent` and preserve setup's choice.

## Discovery

```bash
beaker auth status
beaker github status --repo <owner/repository>
beaker github branches --repo <owner/repository> --json
beaker dataset list --json
beaker dataset show <dataset-name-or-revision> --json
beaker model list --available-only --json
```

`github branches` uses the stored user CLI login. Run `beaker login` only when
that login is missing or expired. Runtime commands use the project credentials
created during setup.

## Launch commands

Ordinary prompt optimization:

```bash
beaker run trigger --ref <branch> --dataset <name@revision> --json
```

Harness Optimization:

```bash
beaker run trigger --ref <branch> --dataset <name@revision> \
  --use-harness-optimization --json
```

Production-system optimize-only:

```bash
beaker run trigger --ref <branch> --dataset <name@revision> \
  --execution-mode optimize_only --json
```

Selected-model benchmark and optimization:

```bash
beaker run trigger --ref <branch> --dataset <name@revision> \
  --optimization-model openai:<model-a> \
  --optimization-model anthropic:<model-b> \
  --execution-mode benchmark_and_optimize \
  --benchmark-split TEST \
  --benchmark-max-cases 30 \
  --final-eval-split VAL \
  --test-all-candidates \
  --json
```

`--ref` reads the remote GitHub ref. It does not push or include local-only
commits or working tree changes.

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
  developer to configure provider credentials or choose ordinary optimization.
- **Unsupported or unavailable model:** rerun
  `beaker model list --available-only --json` and ask the developer to choose
  from that result.
- **Run remains `PREPARING_BUILD` or `QUEUED`:** report the state. It may be
  building the GitHub ref or preparing optimization setup; do not retrigger.
- **Run is `FAILED`:** report `error_message` and the UI link. Do not edit the
  integration unless the developer asks to diagnose or repair it.
- **Cancellation rejects a terminal run:** report the authoritative terminal
  state; do not retry cancellation in a loop.
