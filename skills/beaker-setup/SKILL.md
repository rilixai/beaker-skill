---
name: beaker-setup
description: Set up, configure, or onboard a Python repository as a Beaker prompt-optimization consumer while isolating tooling under .beaker, leaving production runtime behavior unchanged, and never adding or modifying tests. Use when adding Beaker, scaffolding or completing a Beaker @spec factory, configuring beaker.yaml at the repository root or in a nested project, connecting real prompts and labeled datasets, wiring an agent or LLM evaluation path, validating with beaker run dry-run, or preparing a hosted optimization run.
license: MIT
---

# Beaker setup

Turn the repository's real LLM or agent task into a Beaker optimization spec. Find the actual prompt, model call, scorer, and labeled data before completing the integration. Finish with a passing local dry-run when real labeled examples are available; build or launch remotely only when the developer requests it.

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
  production defaults and keep all Beaker imports inside `.beaker/`.

Before changing application code, explain why spec-only integration is
insufficient. Do not refactor production code for Beaker.

## Start safely

1. Inspect the repository for `pyproject.toml`, existing `@spec` factories, `beaker.yaml`, prompt definitions, model/agent calls, evals, and labeled fixtures. In a monorepo, identify the package or service being optimized before choosing the config location; do not assume the Git root.
2. If multiple tasks are plausible, summarize them and ask which one to optimize first.
3. Enter the selected project root, then choose one config location and use it consistently for `init`, agent setup, validation, builds, and runs:

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

## Build the real integration

1. Identify the selected task's input, expected answer, scored fields, prompt targets, and application call path.
2. Derive dataset rows only from real evals, fixtures, files, hosted previews, or examples supplied by the developer. If none exist, stop and request labeled examples or an upload.
3. Replace every `TODO(beaker)` in the selected spec:
   - `_seed_targets`: use the prompts currently sent by the application.
   - `_run_case`: call the real agent/LLM and apply every optimized prompt.
   - scorer: match actual output and ground-truth fields and weights. If it
     uses an LLM judge, set `Spec.llm_scorer_model` to that agent's fixed
     canonical `provider:model`, then route hosted judge calls through
     `scoring_inference_target()` so gateway accounting and run budgets include
     them. The judge model must not follow `runtime.model`; retain the same
     local judge model and normal provider client only for local dry-runs where
     the helper returns `None`. Omit the field for deterministic scorers. If an
     LLM judge exists but its intended model is not established, ask the
     developer rather than choosing a default.
   - data loader and `dataset_schema`: validate the real JSONL row contract.
4. Keep the spec and helper adapters under `.beaker/`. Import application code
   from there; do not move Beaker orchestration into the application package.
5. Return `CaseResult.failed(...)` only when the rollout could not run. Return a normal `CaseResult(output=...)` for an executed but incorrect answer so the scorer can evaluate it.
6. Prove optimized prompts reach the model call with `beaker run dry-run` and,
   when needed, `--strict --trace` plus `beaker trace inspect`. Do not add tests
   or modify the user's existing test suite for Beaker validation.

Read [datasets-and-spec.md](references/datasets-and-spec.md) before deriving data or editing the spec.

## Route models without changing production defaults

Keep Beaker-selected model routing inside `.beaker/` and the evaluation/spec
path. First adapt through the spec or a `.beaker/` adapter. Touch application
code only when no existing injection interface can be reused. If
`runtime.model` is absent, retain the application's existing client and model
defaults.

Read [model-routing-and-tracing.md](references/model-routing-and-tracing.md) when the spec must support model selection, LLM-as-a-judge scoring, framework instrumentation, or trace evidence.

## Authenticate and validate

After the target is known, authenticate with:

```bash
beaker login
beaker agent setup "<Agent Name>" --repo <owner/name>
```

`beaker login` creates or reuses the user-level CLI session. Then run `beaker
agent setup` from the same selected project root and pass the same global
`--config-file`/`BEAKER_CONFIG_FILE` selection used during init. Its positional
value selects an existing agent by name or key, or names a new agent; `--repo`
is required when creating one. If running a later command from the Git root
instead, use the full repository-relative path, for example `--config-file
services/invoices/.beaker/beaker.yaml`. Setup stores the discovered YAML on the
agent as `beaker_config_path` relative to the Git root. Rerunning setup also
synchronizes that path for an existing repository-associated agent. Pass
`--repo` when selecting an unassociated agent so setup can associate it and
store the path. A hosted run can then find a config such as
`services/invoices/.beaker/beaker.yaml` without another path entry.

Agent setup writes runtime secrets only to `.beaker/.env` under the directory
where it runs. Never print, echo, or commit them. Read
[cli-and-hosted-operations.md](references/cli-and-hosted-operations.md) before
credentials, datasets, hosted environment variables, builds, or runs.

Run a local validation only after real labeled examples are available:

```bash
beaker run dry-run --config '{"local_dataset_path":"<dataset-dir>"}'
```

When execution evidence matters, install `beaker-sdk[tracing]`, add `--strict --trace`, run `beaker trace doctor`, and inspect `.beaker/traces` with `beaker trace inspect`.

Read [validation-and-handoff.md](references/validation-and-handoff.md) before declaring setup complete or launching remotely.

## Non-negotiable rules

- Never invent labeled examples from code, schemas, prompts, README text, or plausible domain knowledge.
- Never create a generic repository-named Beaker agent; name the optimization target.
- Never silently choose among multiple plausible tasks.
- Never assume the Git root is the Beaker project root in a monorepo; select the target project and keep its config selection consistent across commands.
- Never place Beaker-owned code or files outside `.beaker/` when they can live there.
- Never create or modify tests, fixtures, snapshots, test helpers, or test configuration for Beaker; existing tests are read-only sources of truth.
- Never import or initialize Beaker from production entrypoints, application startup, request handling, or deployment configuration.
- Never make production execution require Beaker; keep it in development/tooling dependencies when the project supports that separation.
- Never edit application code until spec-only and `.beaker/` adapter approaches have been exhausted; if an edit is unavoidable, add only an optional seam with unchanged defaults and no Beaker imports.
- Never write a real secret outside `.beaker/.env`; use `--value-stdin` for hosted secret values.
- Never leave target prompts only in `_seed_targets`; prove they reach the real model call.
- Never route normal production traffic through Beaker inference.
- Never let a hosted LLM judge bypass `scoring_inference_target()`; direct
  provider clients are only the local dry-run fallback.
- Never set `llm_scorer_model` for a deterministic scorer, infer it from
  `runtime.model`, or invent a default for an LLM judge.
- Never require `runtime.model` for ordinary dry-runs or prompt-only optimization.
- Never use Beaker-owned S3 URIs as user-facing dataset selectors.
- Never trigger a hosted optimization run unless the developer explicitly asks.
- Treat `beaker spec build-from-github`, `beaker dataset upload`, and `beaker agent env ...` as authorized partner operations once their documented preconditions are met.
- Target Python repositories with `pyproject.toml`.
