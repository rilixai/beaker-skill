---
name: beaker-setup
description: Set up, configure, or onboard a Python repository for Beaker agent optimization while isolating evaluation tooling under .beaker, leaving normal runtime behavior unchanged, and never adding or modifying tests. Use when adding Beaker, scaffolding or completing a Beaker @spec factory, selecting the repository files Beaker may optimize, configuring beaker.yaml or spec.required_env, connecting real labeled datasets and an agent or LLM evaluation path, connecting the Beaker GitHub App, validating with beaker run smoke, or launching the first hosted agent optimization run. Also use when preserving an existing logical-target spec that explicitly uses @spec(repository=None).
license: MIT
---

# Beaker setup

Turn the repository's real LLM or agent task into a repository optimization
spec. Find the application entrypoint, candidate source, model call, scorer,
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

## Happy path

Follow this order. The rest of this skill is constraints and recovery.

1. `beaker auth status` (run `beaker login` only if it fails), then `beaker agent list --json`. Use `uvx --from beaker-sdk beaker ...` until the project dependency is installed.
2. Identify the package or service being optimized, not the Git root: in a monorepo that is the directory holding the task's own `pyproject.toml`.
3. Select that project's existing Beaker config, or enter the project root and run `beaker init`.
4. Check the generated `spec.source_dir` right away: it must be the project's Git-root-relative directory, for example `services/invoices`, and `"."` only when the project is the Git root. Fix it immediately if it disagrees; do not wait for a migration hint.
5. Install the `beaker-sdk` dependency command `beaker init` printed, in the project's development/tooling dependency group.
6. After initial discovery, ask all currently known unresolved decisions together, such as which metric to optimize, the labeled-data source, quick-start versus full dataset size, agent name, judge model, or required credentials. Do not wait for discovery to be exhaustive, and continue independent discovery and implementation while the developer responds.
7. Replace every `TODO(beaker)` in the spec and wire the real model call.
8. `beaker agent setup "<Agent Name>"` (add `--spec-id <id>` when the config has several specs). Setup records the agent key in `agent_key` in the selected YAML. A name the developer supplied is approval; do not ask again.
9. Relay newly discovered GitHub, labeled-data, and credential actions as soon as `beaker onboarding status` reports them; ask the developer to begin those actions immediately, then continue independent agent-owned work.
10. Upload or select the labeled dataset, record its immutable selector in the config, confirm required hosted environment values, and validate with `beaker run smoke --strict`.
11. Commit and push once, after the selected config and dataset are final, to `beaker/<YYYYMMDD-HHMM>-<agent-name>`.
12. The first hosted run is a plain `beaker run trigger` (Beaker agent, dataset, optional `--ref`). Do not pass `--optimization-model` unless the developer explicitly asked to compare specific models.
13. Run `beaker onboarding status` after each completed step above, not after read-only probes.

## Keep the onboarding loop explicit

`beaker onboarding status` is the loop-control command for setup:

- Before entering the loop, complete the repository and agent discovery in
  **Start safely**. Select an existing agent's `beaker_config_path` when one
  applies, or establish that no matching agent exists. Status searches upward
  from the working directory; it does not discover nested configs below the
  Git root.
- Run it after a completed onboarding step — `beaker init`, the dependency install, a meaningful spec edit, `beaker agent setup`, the push, dataset selection, smoke, trigger — and whenever the next step is unclear. Do not ask the developer what to do next before consulting this command.
- Do not run it after `--help`, `--print`, a discovery-only `beaker agent list`, or other read-only probes unless you are stuck.
- Follow its single returned next action exactly. The returned action is
  normally the first incomplete agent-owned step in canonical order.
- If `blocked_on_developer` lists developer-owned steps known to be
  incomplete, relay only newly discovered actions verbatim to the developer
  without attempting them yourself, tracking what was already reported in
  this session. Batch the actions currently known, ask the developer to begin
  them immediately, and continue with the returned `next.action` so their work
  overlaps with yours. This report is not a halt.
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
git add -- "<selected-config>" "<spec-and-helper-files>" \
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
possible: config, spec, helper code, credentials, gitignore, and trace receipts. Do
not add Beaker modules under application packages, import or initialize Beaker
from production entrypoints, change deployment/runtime config, add or modify
tests, or route normal traffic through Beaker.

Allow files outside `.beaker/` only when required:

- leave existing source-of-truth datasets where they already live; do not copy
  or move them into `.beaker/`;
- inspect existing tests as read-only evidence when useful, but never create,
  edit, move, or repurpose test files, fixtures, snapshots, or test config;
- record Beaker in development/tooling dependency metadata and its lockfile when
  the project supports that separation;
- add the smallest optional application injection seam only when the spec and
  helper code under `.beaker/` cannot reuse an existing interface. Preserve
  identical production defaults and keep all non-tracing Beaker imports inside
  `.beaker/`. The only application-code exception is narrowly scoped tracing
  wiring: `current_trace()` is a no-op outside a capture, and Beaker remains a
  development/tooling dependency.

Before changing application code, explain why spec-only integration is
insufficient. Do not refactor production code for Beaker.

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
   read its Git-root-relative `spec.source_dir`, and enter that source/project
   root. Do not initialize or scan for a replacement config.
3. Most new users will not have an agent yet. If no agent matches the
   repository, inspect the checkout for
   `pyproject.toml`, existing `@spec` factories, `beaker.yaml`, prompt
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
   `spec.source_dir` is relative to the Git checkout root during hosted builds,
   and `spec.package_import_root` is relative to `source_dir`, not to the YAML.
   For a spec at `services/invoices/.beaker/beaker_spec.py`, use
   `source_dir: services/invoices` and `package_import_root: .beaker`.
   Read [cli-and-hosted-operations.md](references/cli-and-hosted-operations.md)
   before launching any nested-project integration.
5. Never overwrite an existing spec or populated config. Fill the existing integration instead.
6. Install the dependency command printed by `beaker init`, using the project's development/tooling dependency group when supported. Do not make production startup depend on Beaker.

By default, `beaker init` creates `.beaker/beaker.yaml` and, when needed,
`.beaker/beaker_spec.py` under the selected project root. `--config-file` or
`BEAKER_CONFIG_FILE` relocates the YAML inside that project. Init does not create
credentials or placeholder datasets. Persisted `spec.source_dir` values are
always relative to the Git root, not the directory containing the YAML. For
example, initializing `services/invoices` records `source_dir:
services/invoices`; `package_import_root` remains relative to that source
directory. `source_dir: "."` always means the Git root, including when the
selected YAML is nested. Absolute paths and paths containing `..` are invalid.
When smoke or onboarding reports a migration such as `Set source_dir to services/invoices`,
update the existing YAML to that exact repository-relative
value and rerun the failed check; do not move or recreate the config.
Use `--name`, `--task-type`, `--target`, and `--spec-id` when defaults are
ambiguous; use `--discover` to locate existing factories.

Before hosted validation or launch, complete the Beaker YAML preflight in
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md). Check
the hosted source paths, dependency installation, and environment allowlist
against the repository instead of trusting generated defaults. Commit and push
every YAML correction before starting a new run; an existing run does not pick
up later config or agent-setting changes.

Use the selected agent's page to view its runs and score trends.

## Implement the real integration

1. Identify the selected task's input, expected answer, scored fields,
   application call path, and the ordinary source files Beaker may improve.
2. Derive dataset rows only from real evals, fixtures, files, hosted previews, or examples supplied by the developer. If none exist, stop and request labeled examples or an upload.
   When existing labeled data must be converted to JSONL for Beaker, keep the
   converter under `.beaker/`, stage its generated files with
   `tempfile.TemporaryDirectory()`, and invoke `beaker dataset upload` before
   leaving that context. Never save generated JSONL in the user's repository or
   under `.beaker/`. Existing source-of-truth datasets remain in their established
   locations.
3. Replace every `TODO(beaker)` in the selected spec:
   - `@spec`: keep the default repository scope when all eligible ordinary
     source may be optimized, or pass a tuple such as
     `repository=("src/app", "config")` to restrict it. Do not add
     `seed_targets` for repository optimization.
   - `_run_case`: accept `targets=None`, import the real application normally,
     and call the real agent/LLM. Each candidate repository is imported in a
     fresh evaluator process.
   - scorer: score the quality metric the developer chose to hill-climb. If
     the repository does not already establish a single scoring metric (an
     existing eval or scorer with clear fields and weights), ask the developer
     which metric to optimize; never make that decision implicitly. Ask this as
     soon as several plausible scored fields are found; asking is not a halt:
     keep replacing `TODO(beaker)`, wiring `_run_case`, and preparing dataset
     conversion while waiting, then insert the chosen field into the scorer
     when the answer arrives. If it uses an LLM judge, set
     `Spec.llm_scorer_model` to that agent's fixed
     canonical `provider:model`, then route hosted judge calls through
     `scoring_inference_target()` so gateway accounting and run budgets include
     them. The judge model must not follow `runtime.model`; retain the same
     local judge model and normal provider client only for local application or evaluation runs where
     the helper returns `None`. Omit the field for deterministic scorers. If an
     LLM judge exists but its intended model is not established, ask the
     developer rather than choosing a default.
   - data loader and `dataset_schema`: validate the real JSONL row contract.
     Repository-mode case inputs and `CaseResult.output`/`context` must be
     JSON-normalizable because they cross the evaluator process boundary.
   - `spec.required_env`: inspect every application path that hosted candidate
     evaluation can reach, including SDK defaults and fallback branches, and
     list the environment variable names those paths read directly. Do not
     infer this list from existing config alone. Keep local values in
     `.beaker/.env` and hosted values in encrypted agent settings; never put
     values in YAML. Declare a provider key here only for model calls the
     gateway does not serve; gateway-routed calls need no credential setup.
     Before the first hosted run, do not launch until `beaker agent env list`
     confirms that every name in `spec.required_env` is configured on the
     selected agent. If one is missing, ask the developer to configure it in
     the UI or set it with `beaker agent env set NAME --value-stdin`.
4. Keep the spec and helper code under `.beaker/`. Import application code
   from there; do not move Beaker orchestration into the application package.
5. Return `CaseResult.failed(...)` only when the rollout could not run. Return a normal `CaseResult(output=...)` for an executed but incorrect answer so the scorer can evaluate it.
6. Inspect the real call path to verify `_run_case` executes the application
   code inside the selected repository scope, then run `beaker run smoke
   --strict` with either the real local dataset path or the exact hosted
   dataset revision to validate config, spec, dataset, runner, and scorer
   wiring.
   Smoke does not execute `run_case` or the
   scorer and does not support `--trace`. Smoke also warns, without failing,
   when no framework integration or `runtime.trace.model_call` is wired in
   application code; treat that warning as a prompt to finish the tracing
   wiring described in
   [model-routing-and-tracing.md](references/model-routing-and-tracing.md),
   not as a structural failure. When runtime evidence is needed,
   exercise the repository's existing application or evaluation path under a
   local Beaker capture, then use
   `beaker trace doctor --require-model-calls` and
   `beaker trace inspect`. Do not add tests or modify the user's existing test
   suite for Beaker validation.

Read [datasets-and-spec.md](references/datasets-and-spec.md) before deriving data or editing the spec.

## Select the repository optimization surface

`@spec()` now means repository optimization and is equivalent to
`@spec(repository="all")`. The factory, loader, runner, scorer, evidence
provider, and finalizer stay under `.beaker/` and are immutable evaluation
policy. Ordinary application source is the candidate.

Use a normalized tuple of source-relative files or directories to narrow the
editable surface. Agent optimization is the run type; the Beaker agent is the
named target (`beaker agent setup`, `--agent`). Do not use “the agent” for both.

```python
@spec(
    dataset_schema=DATASET_SCHEMA,
    repository=("src/invoice_agent", "config/prompts"),
)
def build_spec(ctx: OptimizationContext) -> Spec:
    return Spec(data_loader=loader, run_case=run_case, scorer=scorer)
```

Hidden paths, `.beaker`, dependency and lock files, build configuration,
vendored or binary files, and files outside the declared scope are protected.
Do not move evaluation policy into editable application source to bypass that
boundary. Repository mode does not accept `Spec.seed_targets`; it passes
`targets=None` to `run_case` and evaluates TEST only after selecting the
winner.

Use `@spec(repository=None)` only for an existing intentional logical-resource
or prompt-target workflow. That mode requires `Spec.seed_targets`. Do not
silently convert one mode into the other.

## Route models without changing production defaults

Keep Beaker-selected model routing inside `.beaker/` and the evaluation/spec
path. First connect through the spec or helper code under `.beaker/`. Touch
application code only when no existing injection interface can be reused. If
`runtime.model` is absent, retain the application's existing client and model
defaults.

For a selected model, prefer the Beaker gateway over the application's provider
keys: point the application's existing client at `inference_target(runtime)`.
The gateway serves every supported provider but takes only the OpenAI Chat
Completions shape, so classify the call site by its SDK surface, not its
provider. Calls it cannot serve keep the application's client and credentials.

Read [model-routing-and-tracing.md](references/model-routing-and-tracing.md) when the spec must support model selection, LLM-as-a-judge scoring, framework instrumentation, or trace evidence.

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

`beaker agent setup` records the selected agent key in `agent_key` in the selected
YAML, so `beaker onboarding status` and `beaker run trigger` select the same
Beaker agent. Add `--spec-id <id>` when the config has several specs. An exported
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
The YAML's `spec.source_dir` independently identifies the Git-root-relative
project source used by both local validation and hosted builds.

Agent setup records the selected agent in `beaker.yaml` but does not provision
runtime secrets. Runtime API keys come from Settings → Credentials → API keys
and should be supplied to CI as `$BEAKER_API_KEY`; local provider and customer
secrets may still live in `.beaker/.env`. Never print, echo, or commit secrets.
Read [cli-and-hosted-operations.md](references/cli-and-hosted-operations.md)
before working with credentials, datasets, hosted environment variables, or
runs.

Before launching, complete the credential preflight in
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md). Derive
required variables from the real `Spec.run_case` call path, then compare them
with `spec.required_env` and `beaker agent env list --agent <selected-agent>`.
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

- Smoke loads and parses the configured dataset. It does not execute a rollout, model call, or scoring call.
- Local-path smoke is offline. Remote-dataset smoke authenticates to Beaker,
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
  agent inside `Spec.run_case` under a local Beaker capture, then run
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
- Never create or modify tests, fixtures, snapshots, test helpers, or test configuration for Beaker; existing tests are read-only sources of truth.
- Never import or initialize Beaker from production entrypoints, application startup, request handling, or deployment configuration, except for narrowly scoped tracing wiring at the real model call site.
- Never make production execution require Beaker; keep it in development/tooling dependencies when the project supports that separation.
- Never edit application code until spec-only and `.beaker/` helper approaches have been exhausted; if an edit is unavoidable, add only an optional seam with unchanged defaults, except for the explicitly allowed tracing wiring.
- Never ask the developer for permission to commit or push the integration;
  `integration_pushed` is agent-owned. The only exception is a developer who
  told you not to take autonomous actions.
- Never push the integration to `main`, `master`, or the default branch unless
  the developer asks; use `beaker/<YYYYMMDD-HHMM>-<agent-name>`.
- Never write a real secret outside `.beaker/.env`; use `--value-stdin` for hosted secret values.
- Never add `seed_targets` to a repository-mode spec or assume `targets` is a
  prompt bundle there; repository mode passes `None`.
- Never leave `@spec(repository=None)` on an existing logical-target spec
  without real `seed_targets` that reach the real model call.
- Never place environment values in `beaker.yaml`; `spec.required_env` contains
  names only.
- Never route normal production traffic through Beaker inference.
- Never let a hosted LLM judge bypass `scoring_inference_target()`; direct
  provider clients are only the local application/evaluation fallback.
- Never instrument scorer, rubric judge, evaluator, post-processing, or
  post-rollout model calls. Candidate tracing covers the workflow rooted at the
  main workflow agent inside `Spec.run_case`, including its sub-agents, tools,
  retrievers, and nested model calls. Scope tracing at the candidate-workflow
  invocation boundary, excluding those calls even when clients or wrappers are
  shared. Scorer traffic is accounted for separately through
  `scoring_inference_target()`.
- Never hand the application or a benchmark harness a transparent proxy,
  `__getattr__` forwarder, or monkeypatched stand-in for its model client.
  Trace at the call site or through a framework integration, and inject only a
  client type the application already accepts; client-type checks reject those
  wrappers and fail every case before it runs. The only exception is a
  framework-specific, type-preserving adapter that subclasses the public client
  base the framework validates, initializes it correctly, delegates its native
  conversion, lifecycle, and request methods, and passes the application's
  resolver or type check before a hosted baseline. When tracing cannot keep that
  type, keep the plain client and report the tracing gap.
- Never set `llm_scorer_model` for a deterministic scorer, infer it from
  `runtime.model`, or invent a default for an LLM judge.
- Never require `runtime.model` for ordinary application/evaluation runs or prompt-only optimization.
- Never use Beaker-owned S3 URIs as user-facing dataset selectors.
- Never trigger a hosted agent optimization run unless the developer explicitly asks.
- The first hosted run is agent optimization of the production system. Launch
  it with a plain `beaker run trigger` (Beaker agent, dataset, optional `--ref`).
  Do not pass `--optimization-model` unless the developer explicitly asked to
  compare specific models. Comparison models currently need
  `@spec(repository=None)` with populated `Spec.seed_targets`; do not add them
  to a repository-mode spec. Do not pass `--test-all-candidates` on that first run.
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
