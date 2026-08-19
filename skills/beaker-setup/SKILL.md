---
name: beaker-setup
description: Set up, configure, or onboard a Python repository for Beaker optimization while isolating evaluation tooling under .beaker, leaving normal runtime behavior unchanged, and never adding or modifying tests. Use when adding Beaker, scaffolding or completing a Beaker @spec factory, selecting the repository files Beaker may optimize, configuring beaker.yaml or spec.required_env, connecting real labeled datasets and an agent or LLM evaluation path, connecting the Beaker GitHub App, validating with beaker run smoke, or preparing a hosted optimization run. Also preserve an existing logical-target spec only when it explicitly uses @spec(repository=None).
license: MIT
---

# Beaker setup

Turn the repository's real LLM or agent task into a repository optimization
spec. Find the application entrypoint, candidate source, model call, scorer,
and labeled data before completing the integration. Finish with a passing local
structural smoke check when real labeled examples are available; launch
remotely only when the developer requests it.

## Keep the onboarding loop explicit

`beaker onboarding status` is the loop-control command for setup. Run it after
every Beaker command and whenever it is unclear what to do next, then follow
its single returned next action exactly. The returned action is normally the
first incomplete agent-owned step in canonical order. If
`blocked_on_developer` lists developer-owned steps known to be incomplete,
relay only newly discovered actions verbatim to the developer without
attempting them yourself, tracking what was already reported in this session.
This report is not a halt: continue with the returned `next.action`. An
`unknown` step has not been checked yet and never means that the developer
must act. Stop and wait only when `next` itself is developer-owned; finish
when `next.id` is `null`. Tracing is advisory but
is returned as the final agent action once no other agent-owned step is
incomplete. Do not ask the developer what to do next before consulting this
command.

## Keep Beaker isolated

Treat Beaker as development/evaluation tooling, not an application runtime.
Keep every Beaker-owned file under the selected project's `.beaker/` whenever
possible: config, spec, adapters, credentials, gitignore, and trace receipts. Do
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
- add the smallest optional application injection seam only when the spec and a
  `.beaker/` adapter cannot reuse an existing interface. Preserve identical
  production defaults and keep all non-tracing Beaker imports inside `.beaker/`.
  The only application-code exception is narrowly scoped trace-adapter wiring:
  `current_trace()` is a no-op outside a capture, and Beaker remains a
  development/tooling dependency.

Before changing application code, explain why spec-only integration is
insufficient. Do not refactor production code for Beaker.

## Start safely

1. Inspect the repository for `pyproject.toml`, existing `@spec` factories, `beaker.yaml`, prompt definitions, model/agent calls, evals, and labeled fixtures. In a monorepo, identify the package or service being optimized before choosing the config location; do not assume the Git root.
2. If multiple tasks are plausible, summarize them and ask which one to optimize first.
3. Enter the selected project root, then choose one config location and use it consistently for `init`, agent setup, validation, and runs:

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
   absolute paths and paths containing `..` are rejected.
4. Never overwrite an existing spec or populated config. Fill the existing integration instead.
5. Install the dependency command printed by `beaker init`, using the project's development/tooling dependency group when supported. Do not make production startup depend on Beaker.

By default, `beaker init` creates `.beaker/beaker.yaml` and, when needed,
`.beaker/beaker_spec.py` under the selected project root. `--config-file` or
`BEAKER_CONFIG_FILE` relocates the YAML inside that project. Init does not create
credentials or placeholder datasets.
Use `--name`, `--task-type`, `--target`, and `--spec-id` when defaults are
ambiguous; use `--discover` to locate existing factories.

Leave `scope_key` absent or unset in `beaker.yaml` by default. Ordinary setups
use the selected agent's default scope; a custom scope is an advanced isolation
option, not a way to distinguish repositories, specs, or repeated setup runs.

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
   - scorer: match actual output and ground-truth fields and weights. If it
     uses an LLM judge, set `Spec.llm_scorer_model` to that agent's fixed
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
   - `spec.required_env`: list only the names of application variables that
     candidate evaluation needs. Keep local values in `.beaker/.env` and
     hosted values in encrypted agent settings; never put values in YAML.
4. Keep the spec and helper adapters under `.beaker/`. Import application code
   from there; do not move Beaker orchestration into the application package.
5. Return `CaseResult.failed(...)` only when the rollout could not run. Return a normal `CaseResult(output=...)` for an executed but incorrect answer so the scorer can evaluate it.
6. Inspect the real call path to verify `_run_case` executes the application
   code inside the selected repository scope, then run `beaker run smoke
   --strict` to validate config, spec, dataset, runner, and scorer wiring.
   Smoke does not execute `run_case` or the
   scorer and does not support `--trace`. Smoke also warns, without failing,
   when no framework adapter or `runtime.trace.model_call` is wired in
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
editable surface:

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
or prompt-target workflow. That mode requires `Spec.seed_targets`, and
selected-model optimizer runs also require those targets. Do not
silently convert one mode into the other.

## Route models without changing production defaults

Keep Beaker-selected model routing inside `.beaker/` and the evaluation/spec
path. First adapt through the spec or a `.beaker/` adapter. Touch application
code only when no existing injection interface can be reused. If
`runtime.model` is absent, retain the application's existing client and model
defaults.

Read [model-routing-and-tracing.md](references/model-routing-and-tracing.md) when the spec must support model selection, LLM-as-a-judge scoring, framework instrumentation, or trace evidence.

## Authenticate, discover the agent, and validate

After the optimization target is known, authenticate and confirm GitHub access:

```bash
beaker auth status
beaker login
beaker onboarding status
beaker github status
```

Skip `beaker login` only when `beaker auth status` confirms the stored session
is valid.

### Connect the Beaker GitHub App

Hosted runs read the repository through the Beaker GitHub App, so the
organization needs an installation before `beaker agent setup` or `beaker run
trigger`.

`beaker github status` is read-only and never opens a browser. Run it first;
exit code 0 means connected, 1 means the connection or repository access is
missing, 2 means the check itself failed. Add `--repo <owner/name>` once the
target repository is known to confirm this installation can read it.

Only the developer can grant access. When status reports a gap, ask them to
complete the install:

```bash
beaker github connect
beaker github connect --repo <owner/name>
```

`beaker github connect` opens the GitHub App install page and then blocks,
polling until the installation appears (`--timeout`, default 600 seconds). Say
plainly that the command is waiting on them, relay the printed install URL
verbatim when the browser cannot open, and let it keep running while they click
through. Do not kill it, background it, or retry it in a loop.

Repository selection happens in GitHub's own picker — all repositories, or an
explicit list — and is not something this skill controls. `--repo` only verifies
afterwards that the chosen repository is readable; it never selects one. If the
installation exists but omits the target repository, `connect --repo` reopens the
install page so the developer can add it. When the repository belongs to an
organization the developer does not administer, an owner must approve the
install request before the command returns.

`beaker agent setup --repo <owner/name>` runs this same connection flow
implicitly and can block on the browser in exactly the same way. Running
`beaker github status` first turns that surprise into a deliberate step.

### Select the agent

Check the existing agents:

```bash
beaker agent list
```

Most new users will not have an agent yet. If none exists, confirm what the
developer wants to optimize and create an agent with a clear name for that
target. Do not use a generic repository name.

If an existing agent clearly matches the task, use it. If several agents could
match, ask the developer which one to use. Tell the developer which agent you
selected before uploading data or launching a run.

Select an existing agent with:

```bash
beaker agent setup "<selected-agent>"
```

Pass `--repo <owner/name>` only when the selected agent still needs that
repository association. To create an agent after confirming its name, run
`beaker agent setup "<New Agent Name>" --repo <owner/name>`. An unknown name
creates an agent, so do not guess one.

Run `beaker agent setup` from the same selected project root and pass the same
global `--config-file`/`BEAKER_CONFIG_FILE` selection used during init. If
running a later command from the Git root instead, use the full
repository-relative path, for example `--config-file
services/invoices/.beaker/beaker.yaml`. Setup stores the discovered YAML on the
agent as `beaker_config_path` relative to the Git root. Rerunning setup also
synchronizes that path for an existing repository-associated agent. A hosted
run can then find a config such as
`services/invoices/.beaker/beaker.yaml` without another path entry.

Agent setup writes runtime secrets only to `.beaker/.env` under the directory
where it runs. Never print, echo, or commit them. Read
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md) before
credentials, datasets, hosted environment variables, or runs. Consult its
scopes section only when the developer explicitly asks for scope isolation.

Before launching, compare `spec.required_env` with `beaker agent env list` for
the selected agent. A hosted run with a missing or empty declared value fails
before candidate dispatch. Set each missing value with `--value-stdin`, then
start a new run.

Run a local validation only after real labeled examples are available:

```bash
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'
```

Smoke loads and parses the configured dataset. It does not execute a rollout, model call, or scoring call. Read its staged `PASS`/`FAIL` output and customer
code traceback when a check fails. A tracing warning in that output is
non-blocking to the CLI, but tracing is a setup-skill completion requirement:
when onboarding returns `tracing_wired` as its final agent action, complete the
wiring before handoff and rerun smoke. When execution evidence matters, run
`beaker trace instrument --check`, exercise the repository's
candidate workflow rooted at the main workflow agent inside `Spec.run_case`
under a local Beaker capture, then run
`beaker trace doctor --require-model-calls` and inspect `.beaker/traces` with
`beaker trace inspect`. Include the workflow's sub-agents, tools, retrievers,
and nested model calls; a judge- or scorer-only capture does not satisfy
runtime trace validation.

Read [validation-and-handoff.md](references/validation-and-handoff.md) before declaring setup complete or launching remotely.

## Non-negotiable rules

- Never invent labeled examples from code, schemas, prompts, README text, or plausible domain knowledge.
- Never create a generic repository-named Beaker agent; name the optimization target.
- Check for existing agents after login. If one clearly matches, use it. If
  several could match, ask the developer which one to use.
- Never attempt to grant GitHub access on the developer's behalf, and never
  guess or pass `--installation-id`; surface the install URL and wait for the
  developer to confirm.
- Never kill, background, or loop-retry `beaker github connect` or `beaker agent
  setup` while it waits for the browser grant; it is polling, not hung.
- Never mention scope, `scope_key`, or `--scope-key` to the developer during
  setup, and never set them unless the developer explicitly asks for scope
  isolation.
- Never silently choose among multiple plausible tasks.
- Never ask the developer what to do next before running `beaker onboarding
  status`; follow its returned action, and relay developer-owned actions
  verbatim.
- Never assume the Git root is the Beaker project root in a monorepo; select the target project and keep its config selection consistent across commands.
- Never place Beaker-owned code or files outside `.beaker/` when they can live there.
- Never save generated JSONL dataset files in the user's repository or under
  `.beaker/`; stage conversions in an OS-managed temporary directory and upload
  them before cleanup.
- Never create or modify tests, fixtures, snapshots, test helpers, or test configuration for Beaker; existing tests are read-only sources of truth.
- Never import or initialize Beaker from production entrypoints, application startup, request handling, or deployment configuration, except for narrowly scoped trace-adapter wiring at the real model call site.
- Never make production execution require Beaker; keep it in development/tooling dependencies when the project supports that separation.
- Never edit application code until spec-only and `.beaker/` adapter approaches have been exhausted; if an edit is unavoidable, add only an optional seam with unchanged defaults, except for the explicitly allowed trace-adapter wiring.
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
- Never set `llm_scorer_model` for a deterministic scorer, infer it from
  `runtime.model`, or invent a default for an LLM judge.
- Never require `runtime.model` for ordinary application/evaluation runs or prompt-only optimization.
- Never use Beaker-owned S3 URIs as user-facing dataset selectors.
- Never trigger a hosted optimization run unless the developer explicitly asks.
- Treat `beaker dataset upload` and `beaker agent env ...` as authorized partner operations once their documented preconditions are met.
- Launch hosted optimization only with `beaker run trigger`. Without `--ref`,
  it prefers the current linked remote branch and falls back to the repository's
  GitHub default branch. Use `--ref <remote-branch>` only for an explicit
  remote branch override. Never pass a tag or commit SHA; the hosted source
  must be a GitHub branch.
- Target Python repositories with `pyproject.toml`.
