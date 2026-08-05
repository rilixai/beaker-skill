# Model routing and tracing

## Model-selection boundary

Treat `runtime.model` as an explicit request for Beaker-controlled model selection in the evaluation path. Its absence means use the application's existing production-like client and model defaults.

Prefer these seams in order:

1. Inject a client/model into an existing eval entrypoint from the spec.
2. Add optional keyword arguments to the nearest agent factory or eval function, preserving existing defaults.
3. Add a small Beaker adapter beside the spec.
4. Modify a central LLM wrapper only when no narrower seam exists.

Example:

```python
from beaker import inference_target

async def _run_case(*, case, targets, runtime):
    prompts = targets.to_dict()
    if runtime.model:
        target = inference_target(runtime)
        model_or_client = build_framework_client(
            base_url=target.base_url,
            api_key=target.api_key,
            model=target.model,
        )
        result = await run_agent_eval(
            case.input,
            prompts=prompts,
            model_or_client=model_or_client,
        )
    else:
        result = await run_agent_eval(case.input, prompts=prompts)
    return CaseResult(output=result.output)
```

The target speaks OpenAI Chat Completions, including SSE streaming with `stream: true`; `stream_options` supports `include_usage`. Do not infer OpenAI Responses or Anthropic Messages support and do not implement a Beaker-specific HTTP envelope.

`inference_target(runtime)` returns generic `base_url`, `api_key`, and `model` settings. Prefer `runtime.canonical_model_id`; the helper may combine an explicit provider and model but does not guess an ambiguous provider.

Do not expose provider keys solely for Beaker-selected runs. Use the run-scoped Beaker gateway credentials. Do not add global environment-driven routing when optional per-call or factory injection is possible.

## Trace evidence

Use `runtime.trace` for concise application stages, artifacts, and handoffs; framework adapters should own model/tool spans. Preserve the application's existing instrumentation and avoid global instrumentation changes.

For evidence-sensitive validation:

```bash
uv add 'beaker-sdk[tracing]'
beaker run dry-run --strict --trace --config '{"local_dataset_path":"<dataset-dir>"}'
beaker trace doctor
beaker trace inspect .beaker/traces
```

Validate both the default-model branch and selected-model branch when feasible. Fail setup clearly if `runtime.model` is present but the selected client cannot be injected.
