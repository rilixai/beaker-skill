---
name: beaker-usage
description: Operate an already-configured Beaker prompt-optimization integration. Use when the developer asks to launch a hosted Beaker run, choose a GitHub branch or dataset, compare or optimize selected models, use Harness Optimization, list or inspect runs, monitor run status, download results, or cancel a run. Do not use to scaffold or repair the Beaker spec; use beaker-setup for setup work.
license: MIT
---

# Beaker usage

Operate the repository's connected Beaker integration through the `beaker`
CLI. Keep this workflow operational: do not edit the spec, application, tests,
datasets, or Beaker config merely to launch or manage a run.

Read [cli-reference.md](references/cli-reference.md) when constructing a launch,
interpreting status exit codes, pulling results, or handling a CLI error.

During setup validation and launch preparation, run `beaker onboarding status`
at the start of the flow and after every CLI command, then follow its returned
action. Relay every known-incomplete action in `blocked_on_developer` verbatim
to the developer and stop instead of attempting developer-owned work. An
`unknown` step has not been checked yet and never means the developer must act.
Tracing is the last agent-owned action when no other agent action remains.
When inspecting, monitoring, pulling, or cancelling a known run whose
documented preconditions are already satisfied, operate the run directly
without restarting onboarding discovery. Consult onboarding status there only
if a command fails or the next action is unclear.

## Stay inside the connected project

1. Locate the selected project's Beaker config. In a monorepo, do not assume
   the Git root is the project root. If several Beaker configs exist and the
   user's target is unclear, show the choices and ask which project to use.
2. Run every command from that project root. If the project uses a non-default
   config path, preserve the same global selector on every command:

   ```bash
   beaker --config-file services/invoices/.beaker/beaker.yaml <command>
   ```

   `BEAKER_CONFIG_FILE` is equivalent. The global option must appear before the
   command group.
3. Treat `.beaker/.env` as secret. Never print, parse, copy, or commit it. Let
   the CLI load credentials.
4. If the config, selected agent, GitHub association, dataset contract, or spec
   is missing or broken, stop the usage workflow and use `$beaker-setup`. Do
   not repair setup incidentally.

For status, listing, result pulls, and cancellation of a known run, execute only
the relevant checks. Do not force the developer through launch discovery again.

## Discover launch inputs without changing state

Before a hosted launch:

1. Confirm the CLI login and the repository connection:

   ```bash
   beaker auth status
   beaker github status --repo <owner/repository>
   ```

   Use `beaker login` only when status says the login is missing or expired.
   GitHub installation or repository access requires developer action; do not
   try to grant it yourself.
2. List GitHub App-visible branches and hosted datasets as JSON:

   ```bash
   beaker github branches --repo <owner/repository> --json
   beaker dataset list --json
   ```

3. Ask which remote GitHub branch to use unless the developer already supplied
   one. Never silently use the current local branch, the default branch, or a
   guessed branch. Verify the chosen branch appears in the GitHub branch
   response. `--ref` resolves GitHub state; unpushed local commits and working
   tree changes are not included.
4. Ask which dataset name or immutable `name@revision` to use unless it is
   already explicit. If the user chooses a bare name, explain that it resolves
   to that dataset's production revision. Never use a storage URI.

If the user explicitly requests a tag or commit instead of a branch, allow it
as `--ref` after restating that exact immutable ref. The normal workflow asks
for a branch.

## Choose the run family explicitly

Do not infer the run family from the repository's model code. If the developer
has not already specified it, ask which outcome they want:

| Run family | Use when | CLI selection |
|---|---|---|
| Ordinary prompt optimization | Optimize the configured production-system path, optionally without an initial benchmark | no model or Harness flags; use `--execution-mode optimize_only` only when explicitly requested |
| Harness Optimization | Use the Codex-driven optimizer rather than the ordinary optimizer | `--use-harness-optimization` |
| Selected-model run | Benchmark, optimize, and compare user-selected models | one to eight `--optimization-model provider:model` flags |

Ordinary optimization preserves the spec's configured model behavior. Do not
ask for models or add `--optimization-model` unless the developer selects a
selected-model run.

Harness Optimization and selected models are mutually exclusive. Never combine
them.

`optimize_only` uses the production system and cannot be combined with
`--optimization-model`, benchmark flags, or final-evaluation flags. If the
developer asks to optimize without an initial benchmark, use
`--execution-mode optimize_only` and skip model discovery.

### Select models and execution mode

For a selected-model run:

1. Discover models whose provider credentials are configured:

   ```bash
   beaker model list --available-only --json
   ```

2. Ask the developer which one to eight canonical `provider:model` values to
   use. Offer only values returned by the command. Do not substitute a similar
   model, infer a default, or choose based on cost or speed without direction.
3. Selected-model runs use `benchmark_and_optimize`; it is also the CLI default
   when models are supplied. The CLI does not expose benchmark-only execution.
4. Use the benchmark defaults unless the developer asks
   to choose the benchmark split or case count. Valid splits are `VAL` and
   `TEST`; valid case counts are 1 through 1000.
5. Add final evaluation splits or `--test-all-candidates` only when the
   developer supplies them or asks to configure them. Do not invent tuning
   values.

Use the typed flags described in the CLI reference. Do not hand-author
`optimization_config` JSON for selected-model runs.

## Authorize and launch

A hosted run can spend money and execute repository code. Before triggering,
state the exact:

- selected project and agent;
- remote GitHub branch or explicit ref;
- dataset reference;
- run family;
- selected models and execution mode, when applicable; and
- non-default benchmark, evaluation, candidate-testing, budget, or scope
  settings.

Launch only after explicit developer authorization. A request such as "launch
this now" that already contains every required choice counts as authorization;
do not ask for redundant confirmation. A request to inspect, plan, or show the
command does not authorize launch.

Prefer JSON output so the run identity is unambiguous:

```bash
# Ordinary prompt optimization
beaker run trigger --ref <branch> --dataset <dataset-ref> --json

# Production-system optimization without an initial benchmark
beaker run trigger --ref <branch> --dataset <dataset-ref> \
  --execution-mode optimize_only --json

# Harness Optimization
beaker run trigger --ref <branch> --dataset <dataset-ref> \
  --use-harness-optimization --json

# Selected-model run
beaker run trigger --ref <branch> --dataset <dataset-ref> \
  --optimization-model <provider:model> \
  --execution-mode benchmark_and_optimize --json
```

Capture the full run `id`, initial `status`, and `web_url` from the JSON. Relay
the full ID and clickable UI URL to the developer. Never shorten the ID.

## List and inspect runs

Recover or filter run IDs with:

```bash
beaker run list --json
beaker run list --status RUNNING --json
```

Check a known run once with:

```bash
beaker run status <full-run-id> --json
```

Interpret exit code `3` as an active run, not a failed command. Exit `0` means
completed, `1` means terminal but unsuccessful, and `2` means a lookup or
client error.

When the developer asks you to monitor until completion, use bounded polling
and remain responsive:

```bash
beaker run status <full-run-id> --watch --poll-interval 15 --poll-timeout 45 --json
```

Report meaningful state changes. Do not start an indefinite foreground poll
that prevents user updates.

## Pull completed results

Pull results only after the run is `COMPLETED`, unless the developer explicitly
asks to inspect partial artifacts:

```bash
beaker run pull <full-run-id> --output-dir .beaker/results/<full-run-id>
```

Check the destination first. Do not overwrite an existing result directory
without permission. The command writes `candidates.json` and
`eval_reports.json`; summarize their paths and the important outcome rather
than dumping large JSON bodies into chat.

## Cancel safely

Cancellation is a state-changing operation:

1. Resolve the exact full run ID. Use `beaker run list --json` when the request
   is ambiguous.
2. State the run ID and current known status.
3. Cancel only when the developer explicitly asks to cancel or stop that run.
   If the request names the exact run and says to cancel it, that is sufficient
   authorization; do not ask twice.
4. Execute the atomic cancellation command without building a direct API call:

   ```bash
   beaker run cancel <full-run-id> --json
   ```

5. Report the authoritative returned status. An already-cancelled run is a
   successful idempotent outcome; completed and failed runs cannot be
   cancelled.

## Non-negotiable rules

- Never launch without an explicit branch/ref, dataset, run family, and
  developer authorization.
- Never silently choose models or use models absent from
  `beaker model list --available-only --json`.
- Never combine selected models with Harness Optimization.
- Never combine selected models with `--execution-mode optimize_only`.
- Never treat unpushed local changes as part of a hosted run.
- Never cancel a run without explicit authorization for the resolved run ID.
- Never expose secrets or bypass the CLI with `curl` or private API calls.
- Never change the spec, application, tests, datasets, agent, scope, or config
  as a side effect of run management.
- Never add a custom scope for an ordinary run. Preserve the configured default
  unless the developer explicitly supplies a scope.
- Never treat status exit code `3` as a failed run.
- Never lose the full run ID or UI link after launch.
- Never ask the developer what to do next before running `beaker onboarding
  status`; use its returned action and relay developer-owned actions verbatim.

## Report the outcome

For a launch, report the branch/ref, dataset, run family, models/mode when
applicable, full run ID, initial status, and UI URL. For status or cancellation,
report the full run ID and authoritative state. For pulled results, report the
destination and a concise result summary.
