---
name: beaker-usage
description: Operate an already-configured Beaker integration. Use when the developer asks to launch agent optimization over a repository or named-resource editable surface, choose a GitHub branch or dataset, pass optional comparison models, verify hosted required environment variables, list or inspect runs, monitor status, download results, or cancel a run. Do not use to scaffold, convert, or repair the Beaker integration; use beaker-setup for setup work.
license: MIT
metadata:
  version: "0.5.0"
  beaker_sdk_version: "0.5.0"
---

# Beaker usage

Operate the repository's connected Beaker integration through the `beaker`
CLI. Keep this workflow operational: do not edit the integration, application, tests,
datasets, CI/CD automation, or Beaker config merely to launch or manage a run.

## Version check

This skill (0.5.0) is written for beaker-sdk 0.5.0; skill and SDK share one
version number and release together. Run `beaker --version` first. If the CLI
is older than 0.5.0 or does not recognize `--version`, upgrade `beaker-sdk`
through the project's development-dependency workflow. If it is newer than
0.5.0, run `npx skills update beaker-usage` and `npx skills update
beaker-setup`, then reload the skill before continuing.

Read [cli-reference.md](references/cli-reference.md) when constructing a launch,
interpreting status exit codes, pulling results, or handling a CLI error.

During setup validation and launch preparation:

- Run `beaker onboarding status` at the start of the flow and after a completed
  onboarding step, not after read-only probes, then follow its returned action.
- Relay only newly discovered actions in `blocked_on_developer` verbatim to
  the developer without attempting developer-owned work, tracking what was
  already reported in this session. Batch the currently known actions, ask the
  developer to begin them immediately, and continue with the returned
  `next.action` so their work overlaps with yours. Do not perform
  `integration_pushed` while `dataset_available` or `required_env_configured`
  is incomplete; wait once no earlier agent work remains.
- An `unknown` step has not been checked yet and never means the developer
  must act. Stop and wait only when `next` itself is developer-owned.
- Complete `dataset_available` and `required_env_configured` before
  `integration_pushed`, the final blocking agent-owned step. Commit and push
  the completed integration once, without asking the developer to confirm
  unless they told you not to take autonomous actions, to a
  `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch in the selected agent repository
  before a hosted optimization run. The agent normally completes dataset
  selection and `experiment_launched` too, but the developer may also complete
  them through the platform UI.
- Tracing is optional: if it applies, make a best effort to include it in
  that push, but never let it block the push; never commit secret files.

When inspecting, monitoring, pulling, or cancelling a known run whose
documented preconditions are already satisfied, operate the run directly
without restarting onboarding discovery. Consult onboarding status there only
if a command fails or the next action is unclear.

## Stay inside the connected project

1. When the selected project is not already known, run `beaker agent list
   --json`, filter agents to an exact `github_repository` match with the current
   GitHub checkout, and select the matching optimization target. Its
   `beaker_config_path` is the authoritative repository-relative config
   location. If several matching agents could fit, show them and ask which
   target to use. Read the selected YAML's Git-root-relative `integrations.<id>.source_dir`
   to locate its project source; do not assume the Git root.
2. Run every command from that project root. If the project uses a non-default
   config path, preserve the same global selector on every command:

   ```bash
   beaker --config-file services/invoices/.beaker/beaker.yaml <command>
   ```

   `BEAKER_CONFIG_FILE` is equivalent. The global option must appear before the
   command group.
3. Treat `.beaker/.env` as secret. Never print, parse, copy, or commit it. Let
   the CLI load credentials.
4. If the config, selected agent, GitHub association, dataset contract, or integration
   is missing or broken, stop the usage workflow and use `$beaker-setup`. Do
   not repair setup incidentally.

Select one `integrations.<id>` entry: explicit `--integration-id`, then
`default_integration`, then the sole entry. If selection is ambiguous, use the
available IDs to identify the intended target. Keep the same ID on
`onboarding status`, `agent env check`, `run smoke`, and `run trigger`.
Agent-key fallback comes from `integrations.<id>.agent_key`;
explicit `--agent` and `BEAKER_AGENT_KEY` take precedence.

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
2. List the available agents. If one clearly matches the task, select it. If
   several could match, ask the developer which one to use. Tell the developer
   which agent you selected before uploading data or launching a run.

   ```bash
   beaker agent list --json
   ```

   Restrict the returned agents to those whose `github_repository` exactly
   matches the current checkout. Carry the selected record's
   `beaker_config_path` as the global `--config-file` selector for commands run
   from the Git root.

3. List GitHub App-visible branches and the selected agent's hosted datasets:

   ```bash
   beaker github branches --repo <owner/repository> --json
   beaker dataset list --agent <selected-agent> --json
   ```

   If the selected integration declares `integrations.<id>.required_env`, compare those names with:

   ```bash
   beaker agent env list --agent <selected-agent>
   ```

   Do not read or print local secret values. If a declared hosted value is
   missing, stop and use `$beaker-setup`; a run would fail before dispatch.

4. Use the CLI's branch selection unless the developer supplied a ref. Without
   `--ref`, `beaker run trigger` uses the current checked-out branch when it
   belongs to the linked repository and exists on its remote, then falls back
   to the repository's GitHub default branch. The command prints the current
   branch when selected locally, or `default branch` when the server selects
   the fallback. Use `--ref <remote-branch>` only for an explicit remote branch
   override, preferably one returned by `beaker github branches`. Unpushed
   local commits and working tree changes are not included.
5. Ask which dataset name or immutable `name@revision` to use unless it is
   already explicit. If the user chooses a bare name, explain that it resolves
   to that dataset's production revision. Never use a storage URI.

Hosted GitHub sources must be remote branches. Tags and commit SHAs passed to
`--ref` return `422` because they cannot serve as pull-request base branches.
If the developer supplies one, ask for a remote branch that points to the
desired commit; do not launch with the tag or SHA.

## Agent optimization and the editable surface

Inspect the selected `Integration.targets` without changing it. Repository
Integrations use `repository(...)` and a `RepositoryRunSetup` class; document
Integrations use `documents(groups=...)` and a `DocumentRunSetup` class.
Both launch with `beaker run trigger` and support model comparison.

The normal first run optimizes the production system. Do not add
`--optimization-model` unless the developer explicitly asks to compare models.
The seed uses the application's configured model behavior. During optimization,
Beaker may change model selection or model-call behavior within the declared
editable surface when that improves the objective.
When model comparison is requested, verify that the evaluation call uses
`runtime.model` through an existing injection seam: a compatible gateway branch
uses `inference_target(runtime)`, while a native client uses its supported model
override. Preserve production defaults otherwise. Initial setup prefers
automatic platform routing, then a compatible gateway, then customer credentials
as a last resort or explicit choice. Neither automatic routing nor the presence
of a configured client proves comparison support; verify that the selected
model reaches the actual request. The usage workflow must not rewrite the
integration to repair routing; direct such work to setup.

Discover allowed models with `beaker model list --available-only --json`.
Repeat `--optimization-model provider:model` for 1–8 distinct selected models.
Keep the same Integration, source branch and immutable dataset for every model.
Do not change the editable surface to make a comparison possible.

TRAIN drives optimization. Without model comparison, TEST measures the selected
winner. Comparisons measure the unchanged setup and each model's seed and
selected winner. Integration runs do not support optional controls for testing
extra candidates or baselines. Do not infer authorization to apply repository
changes or document ChangeSets from permission to run.
For a document winner, review its `document-change-set.json`: creates name a
group and document path; updates/deletes include source IDs and base hashes,
plus source versions when available. Apply only on an explicit request and
only while the current source matches those preconditions.

## Authorize and launch

A hosted run can spend money and execute repository code. Before triggering,
state the exact:

- selected project and Beaker agent;
- remote GitHub branch;
- dataset reference;
- that this is agent optimization;
- comparison models, when the developer asked for them; and
- non-default benchmark, evaluation, or budget settings.

Launch only after explicit developer authorization. A request such as "launch
this now" that already contains every required choice counts as authorization;
do not ask for redundant confirmation. A request to inspect, plan, or show the
command does not authorize launch.

Omit `--ref` for the normal current-branch flow. Pass it only when the developer
selects another remote branch.

Prefer JSON output so the run identity is unambiguous:

```bash
# Agent optimization of the production system
beaker run trigger --agent <selected-agent> --dataset <dataset-ref> --json

# Agent optimization comparing specific models
beaker run trigger --agent <selected-agent> --dataset <dataset-ref> \
  --optimization-model <provider:model> --json
```

Capture the full run `id`, initial `status`, and `web_url` from the JSON. Relay
the full ID and clickable UI URL to the developer. Never shorten the ID. Tell
them immediately that repository setup is finished and the hosted run has
started. Name its current state and make clear that any remaining wait is for
Beaker's hosted results, not more integration work.

An agent may have several active runs, including runs that use the same
selected model. Do not assume a fixed per-agent or per-model run limit.

## List and inspect runs

Use the selected agent's page to view its complete run history and score trends
for completed runs.

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

Report meaningful state changes. While the run remains active, say plainly
that Beaker is still preparing or running it and that you are waiting for more
hosted results; do not imply that repository integration is still underway. Do
not start an indefinite foreground poll that prevents user updates.

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
4. Run the cancellation command:

   ```bash
   beaker run cancel <full-run-id> --json
   ```

5. Report the authoritative returned status. An already-cancelled run is a
   successful idempotent outcome; completed and failed runs cannot be
   cancelled.

## Non-negotiable rules

- Never launch without a resolved remote branch, dataset, and
  developer authorization. The run type is agent optimization.
- State which Beaker agent you selected, and use that same Beaker agent for
  dataset and run commands.
- Never silently choose models or use models absent from
  `beaker model list --available-only --json`.
- Never pass `--optimization-model` unless the developer explicitly asked to
  compare specific models.
- Model comparison requires a configured Integration and an explicit comparison request.

- Never default to a comparison-model run; launch agent optimization of the
  production system unless the developer explicitly asks to benchmark or
  compare specific models.
- When a Beaker agent was set up in another session,
  `beaker run list --agent <key> --json` shows whether it has run before.
- Preserve `Integration.targets`: `repository(...)` optimizes source files and
  `documents(groups=...)` optimizes named content. Both support explicitly
  requested model comparison.
- Never treat unpushed local changes as part of a hosted run.
- Never ask the developer for permission to commit or push the integration
  unless they told you not to take autonomous actions, and never push it to
  `main`, `master`, or the default branch unless the developer asks; use
  `beaker/<YYYYMMDD-HHMM>-<agent-name>`.
- Never pass a tag or commit SHA through `--ref`; hosted GitHub sources accept
  remote branches only.
- Never cancel a run without explicit authorization for the resolved run ID.
- Never expose secrets or bypass the CLI with `curl` or private API calls.
- Never change the integration, application, tests, datasets, agent, or config as a
  side effect of run management.
- Never add tests or CI/CD automation for Beaker: no workflow or pipeline job,
  no pre-commit hook, and no `Makefile`, task-runner, or script entry that runs
  `beaker`. Launch and monitor runs from the CLI instead, and do not run the
  repository's test suite as part of run management.
- Never treat status exit code `3` as a failed run.
- Never lose the full run ID or UI link after launch.
- Never ask the developer what to do next before running `beaker onboarding
  status`; use its returned action and relay developer-owned actions verbatim.

## Report the outcome

For a launch, report the remote branch, dataset, that this is agent
optimization, comparison models when applicable, full run ID, initial status,
and UI URL. For status or cancellation,
report the full run ID and authoritative state. For pulled results, report the
destination and a concise result summary.
When talking to the developer, refer to runs as "run" or "experiment" (for example, `beaker run`).
Call the named target the Beaker agent and the run type agent optimization.
