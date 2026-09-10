---
name: beaker-setup
description: Set up a Python repository with the Beaker Integration contract, connect real labeled data and application execution, and validate setup. Keep evaluation tooling under .beaker and preserve production behavior. Use beaker-usage for operating an already configured integration.
license: MIT
metadata:
  version: "0.5.0"
  beaker_sdk_version: "0.5.0"
---

# Beaker setup

Turn the repository's real LLM or agent task into a repository optimization
integration. Find the application entrypoint, candidate source, model call, scorer,
and labeled data before completing the integration. Finish with a passing local
structural smoke check when real labeled examples are available; launch
remotely only when the developer requests it.

## Load the installed skill first

When the developer asks to install or update this skill, finish that command
before loading and following the newly installed copy. Never install or update
the skill in parallel with loading it. If this session loaded an older copy
before replacement, reload the installed skill; when the agent host cannot
refresh skills in place, start a new agent session instead of continuing with
stale instructions. A user who already has the requested version installed can
load it normally without reinstalling it.

## Version check

This skill (0.5.0) is written for beaker-sdk 0.5.0. The skill and the SDK are
released in lockstep with the same version number, so any difference between
them means one side is stale. Before the happy path, run `beaker --version`
(or `uvx --from 'beaker-sdk>=0.5.0' beaker --version` while Beaker is not yet
installed in the project). If the installed CLI is older than 0.5.0, or does
not recognize `--version`, upgrade `beaker-sdk` through the project's
development-dependency workflow before continuing; older CLIs may lack commands
or flags this skill relies on. If the CLI is newer than 0.5.0, this skill is
stale: run `npx skills update beaker-setup` and `npx skills update
beaker-usage`, then reload the skill as described above. Do not work around a
mismatch by guessing at CLI behavior.

## Happy path

Follow this order. The rest of this skill is constraints and recovery.

1. `beaker auth status` (run `beaker login` only if it fails), then `beaker agent list --json`. Use `uvx --from beaker-sdk beaker ...` until the project dependency is installed.
2. Identify the package or service being optimized, not the Git root: in a monorepo that is the directory holding the task's own `pyproject.toml`.
3. Select that project's existing Beaker config, or enter the project root and run `beaker init`.
4. Check the generated `integrations.<id>.source_dir` right away: it must be the project's Git-root-relative directory, for example `services/invoices`, and `"."` only when the project is the Git root. Fix it immediately if it disagrees.
5. Install the `beaker-sdk` dependency command `beaker init` printed, in the project's development/tooling dependency group.
6. After initial discovery, ask all currently known unresolved decisions together, such as which metric to optimize, the labeled-data source, quick-start versus full dataset size, agent name, judge model, or required credentials. Do not wait for discovery to be exhaustive, and continue independent discovery and implementation while the developer responds. Batching is best effort: if later discovery reveals another required decision, ask it then rather than guessing or delaying current work.
7. Replace every `TODO(beaker)` in the integration and wire the real model call.
8. `beaker agent setup "<Agent Name>"` (add `--integration-id <id>` when the config has several integrations). Setup records the agent key in `integrations.<id>.agent_key`. A name the developer supplied is approval; do not ask again.
9. Relay newly discovered GitHub, labeled-data, and credential actions as soon as `beaker onboarding status` reports them; ask the developer to begin those actions immediately, then continue independent agent-owned work.
10. Upload or select the labeled dataset, retain its immutable `name@revision` or artifact id, pass that same selector explicitly to smoke and launch, confirm required hosted environment values, and validate with `beaker run smoke --strict`. Do not commit an organization-specific dataset selector to YAML by default; a YAML dataset default is optional.
11. Commit and push once, after the selected config and dataset are final, to `beaker/<YYYYMMDD-HHMM>-<agent-name>`.
12. The first hosted run is a plain `beaker run trigger` (Beaker agent, dataset, optional `--ref`). Do not pass `--optimization-model` unless the developer explicitly asked to compare specific models. As soon as it starts, tell the developer that repository setup is finished, name the run state, and make clear that any remaining wait is for Beaker's hosted run rather than more integration work.
13. Run `beaker onboarding status` after each completed step above, not after read-only probes.

## Keep the onboarding loop explicit

`beaker onboarding status` is the loop-control command for setup:

- Before entering the loop, complete the repository and agent discovery in
  **Start safely**. Select an existing agent's `beaker_config_path` when one
  applies, or establish that no matching agent exists. Status searches upward
  from the working directory; it does not discover nested configs below the
  Git root.
- Run it after a completed onboarding step — `beaker init`, the dependency install, a meaningful integration edit, `beaker agent setup`, the push, dataset selection, smoke, trigger — and whenever the next step is unclear. Do not ask the developer what to do next before consulting this command.
- Do not run it after `--help`, `--print`, a discovery-only `beaker agent list`, or other read-only probes unless you are stuck.
- Follow its single returned next action exactly. The returned action is
  normally the first incomplete agent-owned step in canonical order.
- If `blocked_on_developer` lists developer-owned steps known to be
  incomplete, relay only newly discovered actions verbatim to the developer
  without attempting them yourself, tracking what was already reported in
  this session. Batch the actions currently known, ask the developer to begin
  them immediately, and continue with the returned `next.action` so their work
  overlaps with yours. This report is not a halt during independent work. Do
  not perform `integration_pushed` while `dataset_available` or
  `required_env_configured` is incomplete; when no earlier agent work remains,
  wait for those developer actions before the final push.
- An `unknown` step has not been checked yet and never means that the
  developer must act.
- Stop and wait only when `next` itself is developer-owned. Finish when
  `next.id` is `null`.
- Communicate with the developer in plain English. Keep status updates, questions,
  and explanations concise, direct, and free of internal jargon.
- Tracing is optional and advisory: when the selected use case includes
  tracing, make a best effort to wire it and commit its wiring with the
  completed integration before pushing, but never let it block or delay the
  required push.
- `integration_pushed` is the final blocking agent-owned step. Complete
  `dataset_available` and `required_env_configured` before that final push; the
  agent normally completes dataset selection and `experiment_launched` too,
  but the developer may also complete them through the platform UI.

## Commit and push the integration yourself

`integration_pushed` is agent-owned work: commit the completed integration and
push it without asking the developer for confirmation, unless the developer has
told you not to take autonomous actions. Push to a dedicated branch named
`beaker/<YYYYMMDD-HHMM>-<agent-name>`, using the selected Beaker agent's name
slugified, for example `beaker/20260821-1339-invoice-extraction`:

```bash
git checkout -b beaker/$(date +%Y%m%d-%H%M)-invoice-extraction
git status --short
git add -- "<selected-config>" "<integration-and-helper-files>" \
  "<dependency-and-lock-files>" "<intentional-tracing-files>"
git diff --cached --name-only
git commit -m "Add Beaker integration"
git push -u origin HEAD
```

Replace the placeholders with the exact paths changed for this integration.
Include the selected config and target, `.beaker/.gitignore`, dependency
metadata and its lockfile, and any deliberate tracing or application seam.
Do not stage the selected source directory as a whole. Never stage an
unrelated untracked dataset or source file merely to make onboarding pass.
Review the staged path list before committing and ensure every intentional new
integration file is present.

When the checkout is already on a `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch
for the selected agent whose timestamp is less than an hour old, reuse it
instead of creating another one: a retry after a failed or incomplete
integration belongs on the branch already pushed. Older branches, branches for
another agent, and any other branch mean cutting a fresh one. `beaker
onboarding status` names the branch to use in the `integration_pushed` action;
follow it.

Do not push an incomplete integration and then push again only to add the
dataset selector or another known setup change. Upload or select the dataset,
finish the selected config, validate it, and make one final integration push.

Never push the integration to `main`, `master`, or the repository's default
branch, and never open a pull request, unless the developer asks for it. Stage
only integration files; never stage any secret file. Report the branch you
pushed.

## Keep Beaker isolated

Treat Beaker as development/evaluation tooling, not an application runtime.
Keep every Beaker-owned file under the selected project's `.beaker/` whenever
possible: config, integration, helper code, credentials, gitignore, and trace receipts. Do
not add Beaker modules under application packages, import or initialize Beaker
from production entrypoints, change deployment/runtime config, add or modify
tests or CI/CD automation, or route normal traffic through Beaker.

Allow files outside `.beaker/` only when required:

- leave existing source-of-truth datasets where they already live; do not copy
  or move them into `.beaker/`;
- read existing tests as read-only evidence when useful, but never create,
  edit, move, or repurpose test files, fixtures, snapshots, or test config, and
  do not run the repository's test suite during onboarding;
- record Beaker in development/tooling dependency metadata and its lockfile when
  the project supports that separation;
- add the smallest optional application injection seam only when the integration and
  helper code under `.beaker/` cannot reuse an existing interface. Preserve
  identical production defaults and keep all non-tracing Beaker imports inside
  `.beaker/`. The only application-code exception is narrowly scoped tracing
  wiring: `current_trace()` is a no-op outside a capture, and Beaker remains a
  development/tooling dependency.

Before changing application code, explain why integration-only integration is
insufficient. Do not refactor production code for Beaker.

## Write no tests and no CI/CD automation

Beaker onboarding adds no test code and no continuous-integration wiring, and
does not run the repository's test suite. The integration is validated by
`beaker run smoke --strict` and by hosted runs, so there is nothing for a test
suite or a pipeline job to add.

Do not create or modify:

- test files, fixtures, snapshots, test helpers, or test configuration, for the
  integration under `.beaker/` or for anything else;
- CI/CD workflows or jobs, including GitHub Actions workflows, other pipeline
  definitions, and edits to existing ones;
- pre-commit hooks, `Makefile` targets, task-runner entries, or scripts whose
  purpose is to run Beaker automatically.

In particular, do not write a test that imports `beaker_integration.py`, asserts on the
Integration module, loader, or scorer, or runs smoke; and do not add a scheduled or
push-triggered job that runs `beaker run smoke` or `beaker run trigger`.

Running the repository's existing linters, formatters, or type checkers on the
files you changed is allowed. Do not run the repository's test suite as part of
onboarding: it is often slow and proves nothing about the integration, which
`beaker run smoke --strict` validates. Read existing tests for evidence instead.
If the developer explicitly asks for a test or a pipeline job, build only what
they asked for.

## Start safely

1. Determine the enclosing Git root and its GitHub `owner/name`. Check
   authentication and list agents before `beaker init` or the first
   `beaker onboarding status`. Until Beaker is installed in the project, run
   these commands through `uvx`:

   ```bash
   uvx --from beaker-sdk beaker auth status
   uvx --from beaker-sdk beaker login  # only when auth status requires it
   uvx --from beaker-sdk beaker agent list --json
   ```

   Once the project dependency is installed, use its ordinary `beaker`
   command instead.
2. Filter agents to an exact `github_repository` match. If one agent clearly
   matches the task, use its `beaker_config_path`. If several agents could
   match, ask the developer which target to use. From the Git root, select that config,
   read its Git-root-relative `integrations.<id>.source_dir`, and enter that source/project
   root. Do not initialize or scan for a replacement config.
3. Most new users will not have an agent yet. If no agent matches the
   repository, inspect the checkout for
   `pyproject.toml`, existing exported `Integration` values, `beaker.yaml`, prompt
   definitions, model/agent calls, evals, and labeled fixtures. In a monorepo,
   identify the package or service being optimized before choosing the config
   location; do not assume the Git root. If multiple tasks are plausible,
   summarize them and ask which one to optimize first.
4. Only when discovery found no applicable config, enter the selected project
   root and choose one config file for `init`, agent setup, validation, and
   runs:

   ```bash
   cd services/invoices

   # Default location in this project.
   uvx --from beaker-sdk beaker init --print
   uvx --from beaker-sdk beaker init

   # Another path is supported when the developer explicitly wants it.
   uvx --from beaker-sdk beaker --config-file config/beaker.yaml init --print
   uvx --from beaker-sdk beaker --config-file config/beaker.yaml init
   ```

   `BEAKER_CONFIG_FILE=config/beaker.yaml` is equivalent to the global
   `--config-file` option. If Beaker is already installed, omit
   `uvx --from beaker-sdk`. Config paths must be files inside the Git repository;
   absolute paths and paths containing `..` are rejected. Commands may run
   either from the selected project root with its default config, or from the
   Git root with the full repository-relative selector, for example
   `beaker --config-file services/invoices/.beaker/beaker.yaml run smoke --strict`;
   both select the same config. In a monorepo,
   `integrations.<id>.source_dir` is relative to the Git checkout root during hosted builds,
   and `integrations.<id>.package_import_root` is relative to `source_dir`, not to the YAML.
   For an integration at `services/invoices/.beaker/beaker_integration.py`, use
   `source_dir: services/invoices` and `package_import_root: .beaker`.
   Read [cli-and-hosted-operations.md](references/cli-and-hosted-operations.md)
   before launching any nested-project integration.
5. Never overwrite an existing integration or populated config. Fill the existing integration instead.
6. Install the dependency command printed by `beaker init`, using the project's development/tooling dependency group when supported. Do not make production startup depend on Beaker.

By default, `beaker init` creates `.beaker/beaker.yaml` and, when needed,
`.beaker/beaker_integration.py` under the selected project root. `--config-file` or
`BEAKER_CONFIG_FILE` relocates the YAML inside that project. Init does not create
credentials or placeholder datasets. Persisted `integrations.<id>.source_dir` values are
always relative to the Git root, not the directory containing the YAML. For
example, initializing `services/invoices` records `source_dir:
services/invoices`; `package_import_root` remains relative to that source
directory. `source_dir: "."` always means the Git root, including when the
selected YAML is nested. Absolute paths and paths containing `..` are invalid.
When smoke or onboarding reports a path correction such as `Set source_dir to services/invoices`,
update the existing YAML to that exact repository-relative
value and rerun the failed check; do not move or recreate the config.
Use `--agent-key`, `--target`, and `--integration-id` to select explicit init
values; use `--discover` to locate exported Integration values.

Before hosted validation or launch, complete the Beaker YAML preflight in
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md). Check
the hosted source paths, dependency installation, and environment allowlist
against the repository instead of trusting generated defaults. Commit and push
every YAML correction before starting a new run; an existing run does not pick
up later config or agent-setting changes.

Use the selected agent's page to view its runs and score trends.

## Implement the real integration

Use a module-level `integration = Integration(...)` under `.beaker/`. Import
contract types from `beaker`. The integration declares `targets`, a `run_setup`
class, and async `run_case` and `score_case` callables; it holds no run state.

- Declare the real typed dataset row as `run_setup.row_model`. Beaker derives
  the JSON Schema and validates all rows before setup performs I/O.
- Implement async `load_cases(row, *, runtime)` to yield one or more
  `Case(id=..., input=..., expected=...)` values. IDs must be unique across the
  attempt. Stage input files through `runtime.case_files_dir(case_id)` and
  declare them with `CaseFile`.
- Open clients used for case loading or document setup in an async-context-manager
  `prepare_run(*, runtime)`. Beaker owns cleanup. Repository candidates execute in
  a fresh evaluator process; setup clients and in-memory state do not transfer
  to `run_case`. Customer options arrive through `SetupRuntime.config` from
  launch `extra`, supplied per run or through optional `config_defaults.extra`.
- Implement `run_case(*, case_input, runtime)` by calling the real application.
  Return `CaseResult(output=..., output_kind=...)` with a JSON application
  result. Output is retained as the prediction, so keep observed state needed by
  the scorer compact. Use `runtime.trace` for model/tool telemetry.
- Implement `score_case(*, case, result, case_files_dir)` with the real quality
  metric. Return `CaseScore(objective=..., field_scores=..., checks=...)`, with
  passing and failing checks. Ask which metric to optimize and which weights to
  use when the repository does not already establish them;
  continue independent wiring while waiting. Never invent labeled data or scores.

Read [datasets-and-integration.md](references/datasets-and-integration.md)
for typed rows, setup, output/check guidance, and executable examples.

## Select the editable surface

Use `targets=repository()` with a `RepositoryRunSetup` subclass for ordinary
repository optimization. Narrow eligible source with
`repository(("src/invoice_agent", "config/prompts"))` when needed. These are
normalized paths to files or directories relative to the selected integration's
`source_dir`, not the YAML or import root. Beaker protects `.beaker/`, hidden
paths, dependencies, lockfiles, build configuration, vendored and binary files,
and files outside the declared scope. Keep scoring and evaluation policy under
`.beaker/`; do not move it into editable application source to bypass protection.

Use `targets=documents(groups=("wiki",))` with a `DocumentRunSetup` subclass
for an intentional document/resource workflow. Its `prepare_run()` yields
`DocumentRunSetupResult(target_documents=...)` with the real seed documents.
Use `open_candidate(*, targets_dir, scratch_dir)` when the application needs
an index or other runtime object; `run_case` receives it through
`runtime.candidate_runtime`. The candidate document tree is at
`runtime.targets_dir`. Results are create/update/delete `ChangeSet` operations
conditioned on seed content hashes and optional versions; do not auto-apply them.

Both target types support explicitly requested model comparison. Preserve the
selected editable surface; never change it just to enable a run.
The named target is the **Beaker agent**; the run type is **agent optimization**.

## Route models without changing production defaults

Keep Beaker-selected model routing inside `.beaker/` and the evaluation/integration
path. First connect through the integration or helper code under `.beaker/`. Touch
application code only when no existing injection interface can be reused. If
`runtime.model` is absent, retain the application's existing client and model
defaults.

During initial integration, prefer automatic hosted provider routing with
Beaker platform keys. If the setup cannot use it, use the explicit gateway when
an OpenAI Chat Completions-compatible client and the SDK can serve the call.
Use customer clients and credentials as the last resort, or when the developer
explicitly requests them. Do not copy local provider keys into hosted settings
by default; preserve existing hosted credential choices. The explicit gateway
uses platform keys when no agent or organization key is configured.

Identify and wire an optional model/client override during setup when a narrow
injection seam exists, so later comparisons do not require a rewrite. The
current `inference_target(runtime)` helper requires a selected `runtime.model`;
do not invent one for an ordinary run. Automatic routing does not select a
model: comparisons still need injection and verification. Preserve native
request shapes and client types. Do not switch routes to bypass a call failure.

Read [model-routing-and-tracing.md](references/model-routing-and-tracing.md) when the integration must support model selection, LLM-as-a-judge scoring, framework instrumentation, or trace evidence.

## Connect hosted access and validate

**Start safely** already authenticates, discovers the agent, and selects the
config. Do not repeat that discovery unless `beaker onboarding status` reports
that the login or selection is no longer valid. Use the following details only
for the remaining hosted setup.

### Connect the Beaker GitHub App

Hosted runs read the repository through the Beaker GitHub App, so the
organization needs an installation before `beaker agent setup` or `beaker run
trigger`.

- `beaker github status` is read-only and never opens a browser. Run it
  first; exit code 0 means connected, 1 means the connection or repository
  access is missing, 2 means the check itself failed. Add `--repo
  <owner/name>` once the target repository is known to confirm this
  installation can read it.
- Only the developer can grant access. When status reports a gap, ask them to
  complete the install:

  ```bash
  beaker github connect
  beaker github connect --repo <owner/name>
  ```

- `beaker github connect` opens the GitHub App install page and then blocks,
  polling until the installation appears. Say plainly that the command is
  waiting on them, relay the printed install URL verbatim when the browser
  cannot open, and let it keep running while they click through. Do not kill
  it, background it, or retry it in a loop.
- `beaker agent setup --repo <owner/name>` runs this same connection flow
  implicitly and can block on the browser in exactly the same way. Running
  `beaker github status` first turns that surprise into a deliberate step.

Repository selection, install approval, and timeout details are in
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md).

### Select the agent

**Start safely** has already selected an existing agent or established that no
matching agent exists. Tell the developer which agent you selected before
uploading data or launching a run.

Select an existing agent with:

```bash
beaker agent setup "<selected-agent>"
```

`beaker agent setup` records the selected agent key in `integrations.<id>.agent_key`,
so `beaker onboarding status` and `beaker run trigger` select the same
Beaker agent. Add `--integration-id <id>` when the config has several integrations. An exported
`$BEAKER_AGENT_KEY` still overrides the YAML for commands that explicitly need
that behavior. When the developer supplied the agent name, treat it as approval
and do not ask again.

Pass `--repo <owner/name>` only when the selected agent still needs that
repository association. If discovery found no matching agent, create one only
after confirming the optimization target and name:

```bash
beaker agent setup "<New Agent Name>" --repo <owner/name>
```

An unknown name creates an agent, so do not guess one or use a generic
repository name.

Run `beaker agent setup` from the same selected project root and pass the same
global `--config-file`/`BEAKER_CONFIG_FILE` selection used during init. If
running a later command from the Git root instead, use the full
repository-relative path, for example `--config-file
services/invoices/.beaker/beaker.yaml`. Setup stores the discovered YAML on the
agent as `beaker_config_path` relative to the Git root. Rerunning setup also
synchronizes that path for an existing repository-associated agent. A hosted
run can then find a config such as
`services/invoices/.beaker/beaker.yaml` without another path entry.
The YAML's `integrations.<id>.source_dir` independently identifies the Git-root-relative
project source used by both local validation and hosted builds.

Agent setup records the selected agent in `beaker.yaml` but does not provision
runtime secrets. Runtime API keys come from Settings → Credentials → API keys
and can be supplied to a developer-owned CI pipeline as `$BEAKER_API_KEY`; local
provider and customer secrets may still live in `.beaker/.env`. Do not create
that pipeline as part of onboarding. Never print, echo, or commit secrets.
Read [cli-and-hosted-operations.md](references/cli-and-hosted-operations.md)
before working with credentials, datasets, hosted environment variables, or
runs.

Before launching, complete the credential preflight in
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md). Derive
required variables from setup, case loading, candidate initialization, application
execution and scoring paths, then compare them
with `integrations.<id>.required_env` and `beaker agent env list --agent <selected-agent>`.
Provider calls routed through Beaker need no credential setup and never block a
launch. Local shell variables and `.beaker/.env` values are not hosted
settings. Do not trigger a run while a required credential is missing. A
passing smoke check does not prove credentials are ready, because smoke does
not execute `run_case`.

Run structural smoke validation only after real labeled examples are
available. Use the local path when the source data remains on disk:

```bash
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'
```

Use the selected hosted dataset when local data is unavailable or has already
been removed after temporary conversion. Prefer its immutable revision; an
artifact id is equivalent:

```bash
beaker run smoke --strict --agent <selected-agent> --dataset <name@revision>
beaker run smoke --strict --agent <selected-agent> --dataset-id <artifact-id>
```

- Smoke validates typed rows before entering `prepare_run()`, loads cases and checks their files, and validates target documents. For document targets it materializes the seed and enters/closes `open_candidate()` once. All setup resources are closed. It never calls `run_case()` or `score_case()`; setup hooks can perform external I/O.
- Local-path smoke reads local rows; customer setup hooks may still perform external I/O. Remote-dataset smoke authenticates to Beaker,
  resolves the selected snapshot, and downloads it through presigned URLs
  before validating every row. It does not launch a hosted run.
- Use the same immutable `name@revision` or artifact id for smoke and the later
  hosted run. Do not supply `--dataset` and `--dataset-id` together.
- Read its staged `PASS`/`FAIL` output and customer code traceback when a
  check fails.
- A tracing warning in that output is non-blocking to the CLI. When tracing
  applies, make a best effort to complete its wiring as part of the
  integration before the required final push, then rerun smoke; do not let
  tracing block the push.
- When execution evidence matters, run `beaker trace instrument --check`,
  exercise the repository's candidate workflow rooted at the main workflow
  agent inside `Integration.run_case` under a local Beaker capture, then run
  `beaker trace doctor --require-model-calls` and inspect `.beaker/traces`
  with `beaker trace inspect`. Include the workflow's sub-agents, tools,
  retrievers, and nested model calls; a judge- or scorer-only capture does
  not satisfy runtime trace validation.

Read [validation-and-handoff.md](references/validation-and-handoff.md) before declaring setup complete or launching remotely.

## Non-negotiable rules

- Never invent labeled examples from code, schemas, prompts, README text, or plausible domain knowledge.
- Follow the existing-agent decision from **Start safely**. Never create a
  generic repository-named agent or replace a matching agent's selected config.
- Never attempt to grant GitHub access on the developer's behalf, and never
  guess or pass `--installation-id`; surface the install URL and wait for the
  developer to confirm.
- Never kill, background, or loop-retry `beaker github connect` or `beaker agent
  setup` while it waits for the browser grant; it is polling, not hung.
- Treat the selected agent as the direct owner of its runs and run history.
  Create another agent only for a confirmed, distinct optimization target.
- Never silently choose among multiple plausible tasks.
- Never implicitly decide what metric of quality the optimization hill-climbs
  when several metrics are plausible or when scoring aggregates or averages
  multiple metrics; ask the developer which metric and weights to optimize. Ask
  as soon as several plausible scored fields are found. Asking is not a halt:
  keep replacing `TODO(beaker)`, wiring `_run_case`, and preparing dataset
  conversion while waiting, then insert the chosen field into the scorer when
  the answer arrives. A single clearly established metric needs no confirmation.
- Always communicate with the developer in plain English, avoiding internal jargon and technical arcana.
- After repository and agent discovery, never ask the developer what to do next
  before running `beaker onboarding status` with the selected config; follow
  its returned action, and relay developer-owned actions verbatim.
- Never assume the Git root is the Beaker project root in a monorepo; select the target project and keep its config selection consistent across commands.
- Never place Beaker-owned code or files outside `.beaker/` when they can live there.
- Never save generated JSONL dataset files in the user's repository or under
  `.beaker/`; stage conversions in an OS-managed temporary directory and upload
  them before cleanup.
- Never create or modify tests, fixtures, snapshots, test helpers, or test configuration for Beaker; existing tests are read-only sources of truth, and running the repository's test suite is not part of onboarding.
- Never add CI/CD automation for Beaker: no GitHub Actions workflow or other pipeline job, no pre-commit hook, and no `Makefile`, task-runner, or script entry that runs Beaker. Smoke and hosted runs are the validation path. Existing linters and formatters may still be run.
- Never import or initialize Beaker from production entrypoints, application startup, request handling, or deployment configuration, except for narrowly scoped tracing wiring at the real model call site.
- Never make production execution require Beaker; keep it in development/tooling dependencies when the project supports that separation.
- Never edit application code until integration-only and `.beaker/` helper approaches have been exhausted; if an edit is unavoidable, add only an optional seam with unchanged defaults, except for the explicitly allowed tracing wiring.
- Never ask the developer for permission to commit or push the integration;
  `integration_pushed` is agent-owned. The only exception is a developer who
  told you not to take autonomous actions.
- Never push the integration to `main`, `master`, or the default branch unless
  the developer asks; use `beaker/<YYYYMMDD-HHMM>-<agent-name>`.
- Never write a real secret outside `.beaker/.env`; use `--value-stdin` for hosted secret values.
- Preserve the declared repository or document targets during setup.


- Never place environment values in `beaker.yaml`; `integrations.<id>.required_env` contains
  names only.
- Never route normal production traffic through Beaker inference.
- Never let a hosted LLM judge bypass `scoring_inference_target()`; direct
  provider clients are only the local application/evaluation fallback.
- Never instrument scorer, rubric judge, evaluator, post-processing, or
  post-rollout model calls. Candidate tracing covers the workflow rooted at the
  main workflow agent inside `Integration.run_case`, including its sub-agents, tools,
  retrievers, and nested model calls. Scope tracing at the candidate-workflow
  invocation boundary, excluding those calls even when clients or wrappers are
  shared. Scorer traffic is accounted for separately through
  `scoring_inference_target()`.
- Never hand the application or a benchmark harness a transparent Python proxy,
  `__getattr__` forwarder, or monkeypatched stand-in for its model client.
  Trace at the call site or through a framework integration, and inject only a
  client type the application already accepts; client-type checks reject those
  wrappers and fail every case before it runs. The only exception is a
  framework-specific, type-preserving adapter that subclasses the public client
  base the framework validates, initializes it correctly, delegates its native
  conversion, lifecycle, and request methods, and passes the application's
  resolver or type check before a hosted baseline. When tracing cannot keep that
  type, keep the plain client and report the tracing gap.
- Never set `scorer_model` for a deterministic scorer, infer it from
  `runtime.model`, or invent a default for an LLM judge.
- Never require `runtime.model` for ordinary application/evaluation runs or prompt-only optimization.
- Never use Beaker-owned S3 URIs as user-facing dataset selectors.
- Do not commit an organization-specific `dataset_ref` or `dataset_id` to YAML
  by default. Retain the uploaded immutable selector in the onboarding session
  and pass it explicitly to smoke and launch; a repository dataset default is
  an intentional opt-in.
- Never trigger a hosted agent optimization run unless the developer explicitly asks.
- The first hosted run is agent optimization of the production system. Launch
  it with a plain `beaker run trigger` (Beaker agent, dataset, optional `--ref`).
  Do not pass `--optimization-model` unless the developer explicitly asked to
  compare specific models. Comparison models are supported by repository and document Integrations. Do not pass `--test-all-candidates` on that first run.
- Call the named target the **Beaker agent** (`beaker agent setup`, `--agent`)
  and the run type **agent optimization**. Do not use “the agent” for both.
- Before starting a hosted agent optimization run, commit and push the completed
  Beaker integration to a branch in the selected Beaker agent repository. Do not
  commit `*.env` or other secret files. Make a best effort to include tracing
  changes when tracing applies, but never let tracing block the push.
- Treat `beaker dataset upload` and `beaker agent env ...` as authorized partner operations once their documented preconditions are met.
- Launch hosted agent optimization only with `beaker run trigger`. Without `--ref`,
  it prefers the current linked remote branch and falls back to the repository's
  GitHub default branch. Use `--ref <remote-branch>` only for an explicit
  remote branch override. Never pass a tag or commit SHA; the hosted source
  must be a GitHub branch.
- Target Python repositories with `pyproject.toml`.
