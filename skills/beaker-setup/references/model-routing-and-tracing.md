# Model routing and tracing

## Model-selection boundary

Treat `runtime.model` as an explicit request for Beaker-controlled model
selection in the evaluation path. Its absence means use the application's
existing production-like client and model defaults. Keep all Beaker imports for
gateway construction and routing decisions inside `.beaker/`.

The one narrow exception is **trace-adapter wiring**: application model call
sites may import `beaker.tracing` and configure a supported adapter. This is
safe because `current_trace()` returns a `NoopTrace` when no capture is active
(no spans, exporter, or network), and Beaker remains a development/tooling
dependency. This exception does not permit Beaker imports for model selection,
gateway construction, or routing.

Prefer these seams in order:

1. Inject a client/model into an existing interface directly from the spec.
2. Add a small adapter beside the spec under `.beaker/`.
3. Only if both fail, add optional keyword arguments to the nearest agent
   factory or eval function. Preserve existing defaults and do not import
   Beaker from application code, except for the trace-adapter wiring described
   above.

Do not modify a central LLM wrapper, production entrypoint, global environment
routing, or deployment configuration for Beaker. If the application cannot be
evaluated without such changes, stop and explain the limitation instead.

Example:

```python
from beaker import inference_target

async def _run_case(*, case, targets: None, runtime):
    if runtime.model:
        target = inference_target(runtime)
        model_or_client = build_framework_client(
            base_url=target.base_url,
            api_key=target.api_key,
            model=target.model,
        )
        result = await run_agent_eval(
            case.input,
            model_or_client=model_or_client,
        )
    else:
        result = await run_agent_eval(case.input)
    return CaseResult(output=result.output)
```

The target speaks OpenAI Chat Completions, including SSE streaming with `stream: true`; `stream_options` supports `include_usage`. Do not infer OpenAI Responses or Anthropic Messages support and do not implement a Beaker-specific HTTP envelope.

`inference_target(runtime)` returns generic `base_url`, `api_key`, and `model` settings. Prefer `runtime.canonical_model_id`; the helper may combine an explicit provider and model but does not guess an ambiguous provider.

Do not expose provider keys solely for Beaker-selected runs. Use the run-scoped
Beaker gateway credentials. Never add global environment-driven routing for
Beaker.

This example is for the default repository mode. An intentional
`@spec(repository=None)` logical-target spec instead receives its declared
targets and must apply them to the real call. Non-Harness and selected-model
optimizer runs require those `seed_targets`; do not use them with a
repository-only spec.

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

`Spec.llm_scorer_model` plus `scoring_inference_target()` is the accounting path
for LLM-judge traffic; it does not authorize adding the judge to the candidate
workflow trace. Keep rubric judges and scorer calls out of that trace even
when they share a client, wrapper, or framework with the agent.

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
        # ...the repository-mode loader and run_case...
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

### Trace only the candidate workflow

Instrument the candidate workflow rooted at the main workflow agent inside
`Spec.run_case`, including its sub-agents, tools, retrievers, and nested model
calls. Never add Beaker tracing to scorers, rubric judges, evaluators,
post-processing, or post-rollout model calls, even when they use the same
client, wrapper, or framework.

Do not use `current_trace()`, `registered(...)`, `instrument(...)`,
`capabilities(...)`, or `trace.model_call(...)` in scorer, judge, evaluator, or
post-processing code. If the workflow and scorer share an LLM wrapper, scope
tracing at the candidate-workflow invocation boundary so those calls are
excluded. For example, a LiteLLM `registered(...)` scope wraps the complete
candidate workflow, not the judge call.

LLM-judge traffic must still declare `Spec.llm_scorer_model` and use
`scoring_inference_target()` during hosted runs. That provides scorer accounting
and budget enforcement; it does not authorize adding the judge to the candidate
workflow trace.

Use `runtime.trace` in the spec for concise application stages, artifacts, and
handoffs. At application model call sites, use
`from beaker.tracing import current_trace`; `runtime.trace` is not available
there. Preserve the application's existing instrumentation and avoid global
instrumentation changes.

Use an adapter first, scoped only to the candidate-workflow invocation.
Frameworks with an adapter under
`beaker.tracing.integrations` must not be hand-annotated: the supported
frameworks here are PydanticAI and LiteLLM. `beaker trace instrument` detects
the framework and installs its extra; it does not replace the wiring guidance
in this section. Install `beaker-sdk[pydantic-ai]` for PydanticAI or
`beaker-sdk[litellm]` for LiteLLM (the command installs these as needed), rather
than relying only on `beaker-sdk[tracing]`.

For PydanticAI, pass the application's existing instrumentation through
`existing=` so the adapter composes with it:

```python
from beaker.tracing import current_trace
from beaker.tracing.integrations import pydantic_ai

# PydanticAI 1.x
agent = Agent(model, instrument=pydantic_ai.instrument(
    current_trace(), existing=current_instrumentation
))
# PydanticAI 2.x
agent = Agent(model, capabilities=pydantic_ai.capabilities(
    current_trace(), existing=current_capabilities
))
```

On 1.x, `existing` is the application's `instrument=` value; on 2.x it is
the existing `capabilities=` list. Do not pass the adapter's `instrument(...)`
result into `Instrumentation(settings=...)`: that API requires actual
`InstrumentationSettings`, while the adapter returns the existing value
unchanged when no capture is active, which would break production. Use
`capabilities(...)` for the 2.x path. This preserves existing hooks,
instrumentation, and exports without changing global PydanticAI settings.

LiteLLM registration is case-scoped. Keep it around the calls, and flush
afterward because LiteLLM logs after the call returns:

```python
from beaker.tracing import current_trace
from beaker.tracing.integrations.litellm import registered

async with registered(current_trace()) as trace_adapter:
    await litellm.acompletion(model=model, messages=messages)
    await trace_adapter.flush()
```

Use `with registered(current_trace()) as trace_adapter:` around synchronous
`completion(...)` calls and call `trace_adapter.wait()` before leaving the
case. An unflushed or unlogged call is dropped as a capture omission and
downgrades the capture to `incomplete`; do not let the registration scope end
before `flush()` or `wait()`.

For frameworks with no adapter — including provider SDKs, LlamaIndex, and
LangChain today — wrap the real model call with `trace.model_call(...)`.
Wrap nested calls the same way, inside the enclosing operation, so they are
recorded as its child spans. Otherwise the capture can contain stages but zero
model calls, causing `beaker trace doctor --require-model-calls` to fail.

First verify structural wiring:

```bash
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'
```

Smoke verifies structural wiring only; it neither opens a capture nor executes
a model call. It warns, without failing, when no framework adapter or
`runtime.trace.model_call` is wired in application code — resolve that warning
with the wiring above before handoff. Then exercise the repository's normal
application/evaluation path
under a local Beaker capture and validate and inspect the resulting receipt:

```bash
beaker trace instrument --check
beaker trace doctor --require-model-calls
beaker trace inspect .beaker/traces
```

Validate tracing by exercising the candidate workflow rooted at the main
workflow agent inside `Spec.run_case`, including its sub-agents, tools,
retrievers, and nested model calls. A capture containing only judge or scorer
calls does not satisfy runtime trace validation.

Validate both the default-model branch and selected-model branch
through the existing application/evaluation path when feasible. Fail setup
clearly if `runtime.model` is present but the selected client cannot be
injected. Do not add tests for this validation.
