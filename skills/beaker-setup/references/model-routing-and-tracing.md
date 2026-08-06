# Model routing and tracing

## Model-selection boundary

Treat `runtime.model` as an explicit request for Beaker-controlled model
selection in the evaluation path. Its absence means use the application's
existing production-like client and model defaults. Keep all Beaker imports,
gateway construction, and routing decisions inside `.beaker/`.

Prefer these seams in order:

1. Inject a client/model into an existing interface directly from the spec.
2. Add a small adapter beside the spec under `.beaker/`.
3. Only if both fail, add optional keyword arguments to the nearest agent
   factory or eval function. Preserve existing defaults and do not import
   Beaker from application code.

Do not modify a central LLM wrapper, production entrypoint, global environment
routing, or deployment configuration for Beaker. If the application cannot be
evaluated without such changes, stop and explain the limitation instead.

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

Do not expose provider keys solely for Beaker-selected runs. Use the run-scoped
Beaker gateway credentials. Never add global environment-driven routing for
Beaker.

## LLM-as-a-judge scoring

An LLM judge is optimizer-owned traffic, not part of the candidate rollout.
For hosted runs, always construct its OpenAI-compatible client from
`scoring_inference_target(...)`. This uses the runtime-scoped gateway token, so
judge tokens and cost are included automatically in the run ledger and budget.
Do not use the application's normal provider client when this target is
available.

The helper returns `None` during local dry-runs because there is no hosted run
gateway. Only in that case should the scorer retain its existing local provider
client and credentials.

```python
from openai import AsyncOpenAI

from beaker import CaseScore, scoring_inference_target


JUDGE_MODEL = "openai:gpt-4.1-mini"


def _judge_client() -> tuple[AsyncOpenAI, str]:
    target = scoring_inference_target(JUDGE_MODEL)
    if target is not None:
        return AsyncOpenAI(base_url=target.base_url, api_key=target.api_key), target.model
    return AsyncOpenAI(), "gpt-4.1-mini"


class LLMJudgeScorer:
    async def score_case(self, *, case, result) -> CaseScore:
        client, model = _judge_client()
        judgment = await client.chat.completions.create(
            model=model,
            messages=build_judge_messages(case=case, result=result),
        )
        return case_score_from_judgment(judgment)
```

Use an explicit canonical provider/model name such as
`openai:gpt-4.1-mini` or `anthropic:claude-sonnet-4-5`. Adapt the returned
`base_url`, `api_key`, and `model` to the project's existing async client when
it is not OpenAI SDK-based. Keep `score_case` non-blocking.

Exercise both routes through Beaker's dry-run or trace workflow when feasible:
with runtime gateway variables present, verify the judge uses the runtime
target; without them, verify the local provider path remains usable. Do not add
or modify tests for this validation. Hosted setup does not need a provider API
key solely for a judge that uses the runtime gateway.

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
