---
name: beaker-setup
description: Set up, configure, or onboard a Python repository as a Beaker prompt-optimization consumer. Use when adding Beaker, scaffolding or completing a Beaker @spec factory, configuring .beaker/beaker.yaml, connecting real prompts and labeled datasets, wiring an agent or LLM evaluation path, validating with beaker run dry-run, or preparing a hosted optimization run.
---

# Beaker setup

Turn the repository's real LLM or agent task into a Beaker optimization spec. Find the actual prompt, model call, scorer, and labeled data before completing the integration. Finish with a passing local dry-run when real labeled examples are available; build or launch remotely only when the developer requests it.

## Start safely

1. Inspect the repository for `pyproject.toml`, existing `@spec` factories, `.beaker/beaker.yaml`, prompt definitions, model/agent calls, evals, and labeled fixtures.
2. If multiple tasks are plausible, summarize them and ask which one to optimize first.
3. Preview deterministic scaffolding before writing:

   ```bash
   uvx --from beaker-sdk beaker init --print
   uvx --from beaker-sdk beaker init
   ```

   If Beaker is already installed, use `beaker init --print` and `beaker init`.
4. Never overwrite an existing spec or populated config. Fill the existing integration instead.
5. Install the dependency command printed by `beaker init` so future commands use the project's pinned package.

`beaker init` creates `.beaker/beaker.yaml` and, when needed, `.beaker/beaker_spec.py`. It does not create credentials or placeholder datasets. Use `--name`, `--task-type`, `--target`, and `--spec-id` when defaults are ambiguous; use `--discover` to locate existing factories.

## Build the real integration

1. Identify the selected task's input, expected answer, scored fields, prompt targets, and application call path.
2. Derive dataset rows only from real evals, fixtures, files, hosted previews, or examples supplied by the developer. If none exist, stop and request labeled examples or an upload.
3. Replace every `TODO(beaker)` in the selected spec:
   - `_seed_targets`: use the prompts currently sent by the application.
   - `_run_case`: call the real agent/LLM and apply every optimized prompt.
   - scorer: match actual output and ground-truth fields and weights.
   - data loader and `dataset_schema`: validate the real JSONL row contract.
4. Return `CaseResult.failed(...)` only when the rollout could not run. Return a normal `CaseResult(output=...)` for an executed but incorrect answer so the scorer can evaluate it.
5. Add a smoke assertion or captured-call test proving optimized prompts reach the model call.

Read [datasets-and-spec.md](references/datasets-and-spec.md) before deriving data or editing the spec.

## Route models without changing production defaults

Keep Beaker-selected model routing inside the evaluation/spec path. If `runtime.model` is absent, retain the application's existing client and model defaults. If it is present, adapt `inference_target(runtime)` to the framework's existing client type through the narrowest available injection seam.

Read [model-routing-and-tracing.md](references/model-routing-and-tracing.md) when the spec must support model selection, framework instrumentation, or trace evidence.

## Authenticate and validate

After the target is known, authenticate with:

```bash
beaker auth status
beaker login --agent --agent-name "<Agent Name>" --repo <owner/name>
```

This writes secrets only to `.beaker/.env`. Never print, echo, or commit them. Read [cli-and-hosted-operations.md](references/cli-and-hosted-operations.md) before credentials, datasets, hosted environment variables, builds, or runs.

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
- Never write a real secret outside `.beaker/.env`; use `--value-stdin` for hosted secret values.
- Never leave target prompts only in `_seed_targets`; prove they reach the real model call.
- Never route normal production traffic through Beaker inference.
- Never require `runtime.model` for ordinary dry-runs or prompt-only optimization.
- Never use Beaker-owned S3 URIs as user-facing dataset selectors.
- Never trigger a hosted optimization run unless the developer explicitly asks.
- Treat `beaker spec build-from-github`, `beaker dataset upload`, and `beaker agent env ...` as authorized partner operations once their documented preconditions are met.
- Target Python repositories with `pyproject.toml`.
