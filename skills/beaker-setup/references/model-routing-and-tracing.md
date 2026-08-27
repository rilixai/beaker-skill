# Model routing and tracing

## Prefer the gateway over application provider keys

When the evaluation path selects a model, point the application's *existing*
client at `inference_target(runtime)` instead of giving the run a provider key.

Gateway-routed calls require no credential setup at all. The gateway picks the
agent key, then the organization key, then the platform key, and the platform
key covers OpenAI, Anthropic, Google, and OpenRouter. So declare no provider
key in `spec.required_env` for these calls, never create an agent or
organization provider key for the developer, and never treat a missing one as a
launch blocker. Those keys are a billing choice the customer makes in the UI.

That order is a selection, not a retry chain. The gateway picks the first
configured key before the call and does not move on if the provider rejects it,
so a configured but broken agent or organization key fails instead of reaching
the platform key.

A direct provider call from application code has no platform fallback. It runs
only on a key the developer configured and the spec declares. That is the cost
of not routing through the gateway.

The gateway serves every provider Beaker supports and rewrites each request for
that provider, so the model or provider is not the constraint: the request
shape is. The gateway accepts the OpenAI Chat Completions shape. Sort the call
site by the SDK it calls, not by its provider:

| Application call site | Beaker integration |
| --- | --- |
| OpenAI SDK chat completions, OpenRouter with an effort word, or a LiteLLM-style wrapper | Repoint `base_url` and `api_key` at the target. Nothing else changes. |
| A reasoning *budget* (`reasoning.max_tokens`, Anthropic `budget_tokens`, Gemini `thinkingBudget`) | Same repoint, and send the nearest effort word in place of the budget. The gateway takes effort words only. |
| Another request shape (OpenAI Responses, Anthropic Messages, native Gemini) | The gateway does not serve these for candidate rollouts. Keep the application's client and credentials, declare them in `spec.required_env`, and say so at handoff. |

Do not rewrite a working call site into the OpenAI shape just to reach the
gateway; that changes production code. Reuse the existing injection seam, and
take the third row when the shape does not fit.

## Model-selection boundary

Treat `runtime.model` as an explicit request for Beaker-controlled model
selection in the evaluation path. Its absence means use the application's
existing production-like client, model defaults, and credentials.
`inference_target(runtime)` requires both a selected model and hosted run
credentials, and raises otherwise, so ordinary application/evaluation runs and
prompt-only optimization are not gateway-routed. Keep all Beaker imports for
gateway construction and routing decisions inside `.beaker/`.

The one narrow exception is **tracing integration**: application model call
sites may import `beaker.tracing` and configure supported instrumentation. This
is safe because `current_trace()` returns a `NoopTrace` when no capture is active
(no spans, exporter, or network), and Beaker remains a development/tooling
dependency. This exception does not permit Beaker imports for model selection,
gateway construction, or routing.

Prefer these seams in order:

1. Inject a client/model into an existing interface directly from the spec.
2. Add a small adapter beside the spec under `.beaker/`.
3. Only if both fail, add optional keyword arguments to the nearest agent
   factory or eval function. Preserve existing defaults and do not import
   Beaker from application code, except for the tracing wiring described
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

Build the injected client as a type the application already constructs and
accepts. Applications and benchmark harnesses often check the client they are
handed against known types, so a Beaker-specific object or a wrapper around the
client is rejected before any case runs. Change the endpoint, not the client
type or the call shape.

The target speaks OpenAI Chat Completions, including SSE streaming with `stream: true`; `stream_options` supports `include_usage`. Any supported provider's models are reachable through that one shape, so do not add a provider-specific gateway path: do not infer OpenAI Responses or Anthropic Messages support and do not implement a Beaker-specific HTTP envelope.

`inference_target(runtime)` returns generic `base_url`, `api_key`, and `model` settings. Prefer `runtime.canonical_model_id`; the helper may combine an explicit provider and model but does not guess an ambiguous provider.

Do not expose provider keys solely for Beaker-selected runs. Use the run-scoped
Beaker gateway credentials, and remove such a name from `spec.required_env`
once its calls are gateway-routed. Never add global environment-driven routing
for Beaker.

This example is for the default repository mode. An intentional
`@spec(repository=None)` logical-target spec instead receives its declared
targets and must apply them to the real call. Selected-model optimizer runs
require those `seed_targets`; do not use them with a repository-only spec.

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

### Preserve the client type

Tracing must not change the type or identity of any object the application
hands to a framework, agent factory, or benchmark harness. Add tracing only at
the integration entrypoints in the table below, or with `trace.model_call(...)`
around the call site. Never put a proxy, subclass, `__getattr__` forwarder, or
monkeypatched method in place of the client or model object. Client-type checks
reject the wrapper, and every case then fails before it runs.
Wrap the *call*, not the client.

If tracing cannot be wired without changing that type, keep the original
unwrapped client, run untraced, and report the tracing gap at handoff. An
unresolved tracing warning never blocks handoff; a rejected client fails the
whole run.

### Framework integrations

Use a built-in framework integration first, scoped only to the candidate-workflow
invocation. A framework in this list has built-in integration under
`beaker.tracing.integrations` and must not be hand-annotated: the integration
owns that framework's spans — agent and node runs, model calls, tool calls, and
handoffs — so do not wrap those calls in `runtime.trace.model_call(...)` as well.
`runtime.trace` stays for application-level stages and artifacts.

| Framework | Extras | Wiring entrypoint |
| --- | --- | --- |
| PydanticAI | `beaker-sdk[tracing,pydantic-ai]` | `pydantic_ai.instrument(...)` (1.x) or `pydantic_ai.capabilities(...)` (2.x) |
| LangChain / LangGraph | `beaker-sdk[tracing,langchain]` | `langchain.config(...)` passed as the invocation `config=` |
| LiteLLM | `beaker-sdk[tracing,litellm]` | `litellm.registered(...)` scope around the calls |
| OpenAI Agents SDK | `beaker-sdk[tracing,openai-agents]` | `openai_agents.registered(...)` scope around the run |

`beaker trace instrument` detects the framework and installs its extras; it does
not replace the wiring guidance in this section. Install the framework extras
above rather than relying only on `beaker-sdk[tracing]`.

Every integration takes the application's existing telemetry through `existing=`
and composes with it, so an app's own OpenInference, LangSmith, or Logfire
instrumentation keeps working; no integration patches global state.

For PydanticAI, pass the application's existing instrumentation through
`existing=` so Beaker composes with it:

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
the existing `capabilities=` list. Do not pass the `instrument(...)`
result into `Instrumentation(settings=...)`: that API requires actual
`InstrumentationSettings`, while the helper returns the existing value
unchanged when no capture is active, which would break production. Use
`capabilities(...)` for the 2.x path. This preserves existing hooks,
instrumentation, and exports without changing global PydanticAI settings.

For LangChain and LangGraph, wire the integration into the invocation config so the
callback is scoped to that call:

```python
from beaker.tracing import current_trace
from beaker.tracing.integrations import langchain as beaker_langchain

result = graph.invoke(
    state, config=beaker_langchain.config(current_trace(), existing=app_config)
)
```

In the spec, pass `runtime.trace` instead of `current_trace()`. `config(...)`
preserves every other `RunnableConfig` key, including the app's own
`callbacks`, so an existing OpenInference or LangSmith handler keeps exporting;
the integration only adds a callback and patches nothing globally. With
`stream()`/`astream()`, keep the capture open until the iterator is fully
consumed: spans still open when the capture closes are dropped as capture
omissions and downgrade the capture to `incomplete`.

LiteLLM registration is case-scoped. Keep it around the calls, and flush
afterward because LiteLLM logs after the call returns:

```python
from beaker.tracing import current_trace
from beaker.tracing.integrations.litellm import registered

async with registered(current_trace()) as litellm_trace:
    await litellm.acompletion(model=model, messages=messages)
    await litellm_trace.flush()
```

Use `with registered(current_trace()) as litellm_trace:` around synchronous
`completion(...)` calls and call `litellm_trace.wait()` before leaving the
case. An unflushed or unlogged call is dropped as a capture omission and
downgrades the capture to `incomplete`; do not let the registration scope end
before `flush()` or `wait()`.

For frameworks absent from the list above — including provider SDKs and
LlamaIndex today — wrap the real model call with `trace.model_call(...)`.
Wrap nested calls the same way, inside the enclosing operation, so they are
recorded as its child spans. Otherwise the capture can contain stages but zero
model calls, causing `beaker trace doctor --require-model-calls` to fail.

First verify structural wiring with the real local dataset or the exact hosted
snapshot selected for launch:

```bash
beaker run smoke --strict --config '{"local_dataset_path":"<dataset-dir>"}'
beaker run smoke --strict --agent <selected-agent> --dataset <name@revision>
```

Smoke verifies structural wiring only; it neither opens a capture nor executes
a model call. It warns, without failing, when no framework integration or
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
