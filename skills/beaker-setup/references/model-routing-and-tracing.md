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
Declare its model once on the agent's `Spec` with the optional
`llm_scorer_model` field. Use a canonical `provider:model` value such as
`openai:gpt-4.1-mini` or `anthropic:claude-sonnet-4-5`. Omit the field when the
scorer is deterministic. If the repository or developer has not established
which model an LLM judge should use, ask instead of choosing a default.

The scorer model is evaluation policy for this agent. It stays fixed when
Beaker evaluates different `runtime.model` values and when the application runs
through its normal client/model path with no selected runtime model. Never copy
or derive `llm_scorer_model` from `runtime.model`; different agents may declare
different judge models.

For hosted runs, always construct its OpenAI-compatible client from
`scoring_inference_target()`. This uses a scorer-scoped gateway token backed by
the platform's existing provider credentials, so
judge tokens and cost are included automatically in the run ledger and budget.
Do not use the application's normal provider client when this target is
available.

The helper returns `None` during local application or evaluation runs because
there is no hosted run gateway. Only in that case should the scorer retain its
existing local provider client and credentials. The structural smoke check does
not call the scorer.

```python
from openai import AsyncOpenAI

from beaker import CaseScore, Spec, scoring_inference_target


JUDGE_MODEL = "openai:gpt-4.1-mini"
LOCAL_JUDGE_MODEL = "gpt-4.1-mini"


def _judge_client() -> tuple[AsyncOpenAI, str]:
    target = scoring_inference_target()
    if target is not None:
        return AsyncOpenAI(base_url=target.base_url, api_key=target.api_key), target.model
    return AsyncOpenAI(), LOCAL_JUDGE_MODEL


class LLMJudgeScorer:
    async def score_case(self, *, case, result) -> CaseScore:
        client, model = _judge_client()
        judgment = await client.chat.completions.create(
            model=model,
            messages=build_judge_messages(case=case, result=result),
        )
        return case_score_from_judgment(judgment)


def build_spec() -> Spec:
    return Spec(
        # ...the agent's seed targets, loader, and run_case...
        scorer=LLMJudgeScorer(),
        llm_scorer_model=JUDGE_MODEL,
    )
```

Adapt the returned `base_url`, `api_key`, and `model` to the project's existing
async client when it is not OpenAI SDK-based. Keep `score_case` non-blocking.
Keep the local fallback on the same judge model declared by the spec, translating
only the provider-specific model syntax when the local SDK requires it.

Exercise both routes through an existing application/evaluation or trace
workflow when feasible: with runtime gateway variables present, verify the judge
uses the runtime target; without them, verify the local provider path remains
usable. Do not add or modify tests for this validation. `beaker run smoke` is
structural and does not execute either route. Hosted setup does not need a
provider API key solely for a judge that uses the runtime gateway.

## Trace evidence

Use `runtime.trace` for concise application stages, artifacts, and handoffs; framework adapters should own model/tool spans. Preserve the application's existing instrumentation and avoid global instrumentation changes.

For evidence-sensitive validation:

```bash
uv add 'beaker-sdk[tracing]'
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'
# Exercise the repository's normal agent/evaluation path under a local Beaker capture.
beaker trace doctor
beaker trace inspect .beaker/traces
```

Smoke verifies structural wiring only; it neither opens a capture nor executes a
model call. Validate both the default-model branch and selected-model branch
through the existing application/evaluation path when feasible. Fail setup
clearly if `runtime.model` is present but the selected client cannot be injected.
