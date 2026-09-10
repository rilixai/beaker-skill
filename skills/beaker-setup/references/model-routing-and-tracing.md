# Model routing and tracing

## Prefer the gateway over application provider keys

When the evaluation path selects a model, point the application's *existing*
client at `inference_target(runtime)` instead of giving the run a provider key.

Gateway-routed calls require no credential setup at all. The gateway picks the
agent key, then the organization key, then the platform key, and the platform
key covers OpenAI, Anthropic, Google, and OpenRouter. So declare no provider
key in `integrations.<id>.required_env` for these calls, never create an agent or
organization provider key for the developer, and never treat a missing one as a
launch blocker. Those keys are a billing choice the customer makes in the UI.

That order is a selection, not a retry chain. The gateway picks the first
configured key before the call and does not move on if the provider rejects it,
so a configured but broken agent or organization key fails instead of reaching
the platform key.

A direct provider call from application code has no platform fallback. It runs
only on a key the developer configured and the integration declares. That is the cost
of not routing through the gateway.

The gateway serves every provider Beaker supports and rewrites each request for
that provider, so the model or provider is not the constraint: the request
shape is. The gateway accepts the OpenAI Chat Completions shape. Sort the call
site by the SDK it calls, not by its provider:

| Application call site | Beaker integration |
| --- | --- |
| OpenAI SDK chat completions, OpenRouter with an effort word, or a LiteLLM-style wrapper | Repoint `base_url` and `api_key` at the target. Nothing else changes. |
| A reasoning *budget* (`reasoning.max_tokens`, Anthropic `budget_tokens`, Gemini `thinkingBudget`) | Same repoint, and send the nearest effort word in place of the budget. The gateway takes effort words only. |
| Another request shape (OpenAI Responses, Anthropic Messages, native Gemini) | The gateway does not serve these for candidate rollouts. Keep the application's client and credentials, declare them in `integrations.<id>.required_env`, and say so at handoff. |

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

1. Inject a client/model into an existing interface directly from the integration.
2. Add a small adapter beside the integration under `.beaker/`.
3. Only if both fail, add optional keyword arguments to the nearest agent
   factory or eval function. Preserve existing defaults and do not import
   Beaker from application code, except for the tracing wiring described
   above.

Do not modify a central LLM wrapper, production entrypoint, global environment
routing, or deployment configuration for Beaker. If the application cannot be
evaluated without such changes, stop and explain the limitation instead.

Example:

```python
from beaker import CaseResult, inference_target

async def _run_case(*, case_input, runtime):
    if runtime.model:
        target = inference_target(runtime)
        model_or_client = build_framework_client(
            base_url=target.base_url,
            api_key=target.api_key,
            model=target.model,
        )
        result = await run_agent_eval(
            case_input,
            model_or_client=model_or_client,
        )
    else:
        result = await run_agent_eval(case_input)
    return CaseResult(output=result.output)
```

Build the injected client as a type the application already constructs and
accepts. Applications and benchmark harnesses often check the client they are
handed against known types, so a Beaker-specific object or a wrapper around the
client is rejected before any case runs. Change the endpoint, not the client
type or the call shape.

The target speaks OpenAI Chat Completions, including SSE streaming with `stream: true`; `stream_options` supports `include_usage`. Any supported provider's models are reachable through that one shape, so do not add a provider-specific gateway path: do not infer OpenAI Responses or Anthropic Messages support and do not implement a Beaker-specific HTTP envelope.

`inference_target(runtime)` returns generic `base_url`, `api_key`, and `model` settings. `RolloutRuntime.model` contains the selected canonical `provider:model`; the helper does not invent a model when it is absent.

Do not expose provider keys solely for Beaker-selected runs. Use the run-scoped
Beaker gateway credentials, and remove such a name from `integrations.<id>.required_env`
once its calls are gateway-routed. Never add global environment-driven routing
for Beaker.

For document integrations, also use the candidate documents or runtime object
provided through `runtime.targets_dir` or `runtime.candidate_runtime`.

## LLM-as-a-judge scoring

Configure a fixed judge independently from the compared model:

```yaml
config_defaults:
  scorer_model: openai:gpt-4.1-mini
```

Only set this for an actual LLM judge and a developer-approved model; never
infer it from `runtime.model`. In `score_case`, use
`scoring_inference_target()` to obtain the dedicated hosted scorer gateway.
This accounts for judge traffic separately from candidate execution. When
it returns `None` locally, retain the application's own judge client and
credentials. Keep the same judge model in local evaluation.

```python
from beaker import scoring_inference_target

async def call_judge(question):
    target = scoring_inference_target()
    if target is None:
        return await existing_local_judge(question)
    client = build_judge_client(
        base_url=target.base_url, api_key=target.api_key, model=target.model,
    )
    return await client.judge(question)
```

Candidate tracing covers the application workflow, including nested model and
tool calls. Do not instrument scorer or judge calls as candidate activity.

## Trace evidence

### Trace only the candidate workflow

Instrument the candidate workflow rooted at the main workflow agent inside
`Integration.run_case`, including its sub-agents, tools, retrievers, and nested model
calls. Never add Beaker tracing to scorers, rubric judges, evaluators,
post-processing, or post-rollout model calls, even when they use the same
client, wrapper, or framework.

Do not use `current_trace()`, `registered(...)`, `instrument(...)`,
`capabilities(...)`, or `trace.model_call(...)` in scorer, judge, evaluator, or
post-processing code. If the workflow and scorer share an LLM wrapper, scope
tracing at the candidate-workflow invocation boundary so those calls are
excluded. For example, a LiteLLM `registered(...)` scope wraps the complete
candidate workflow, not the judge call.

LLM-judge traffic must still declare `config_defaults.scorer_model` and use
`scoring_inference_target()` during hosted runs. That provides scorer accounting
and budget enforcement; it does not authorize adding the judge to the candidate
workflow trace.

Use `runtime.trace` in the integration for concise application stages, artifacts, and
handoffs. At application model call sites, use
`from beaker.tracing import current_trace`; `runtime.trace` is not available
there. Preserve the application's existing instrumentation and avoid global
instrumentation changes.

When the application or harness executes tools itself (its own dispatch loop,
no framework from the table below), wrap that dispatch in
`current_trace().tool_call(name, arguments=..., call_id=...)` and record the
result with `call.output(...)`. Without tool spans Beaker only knows which tools
the model *asked* for (read off the model response), never what they returned,
how long they took, or whether they raised, so the optimizer sees requests, not
executions. Pass only the model-visible arguments; keep injected state such as
simulator handles or credentials out of `arguments`.

### Preserve the client type

Tracing must not change the type or identity of any object the application
hands to a framework, agent factory, or benchmark harness. Add tracing only at
the integration entrypoints in the table below, or with `trace.model_call(...)`
around the call site. Do not put a transparent proxy, `__getattr__` forwarder,
or monkeypatched method in place of the client or model object. Client-type
checks reject such wrappers, and every case then fails before it runs.
Wrap the *call*, not the client, unless the framework requires a client wrapper
and the type-preserving adapter described below is necessary.

If tracing cannot be wired without changing that type, keep the original
unwrapped client, run untraced, and report the tracing gap at handoff. The only
exception is a framework-specific adapter that preserves the exact public base
type the framework validates. An unresolved tracing warning never blocks
handoff; a rejected client fails the whole run.

When a benchmark or agent harness owns the loop and takes the client object as
a parameter (no framework from the table below is involved, so no integration
sees the calls), that adapter is a subclass of the harness's own client class
that overrides the single method every turn goes through and wraps only the
`super()` call in `current_trace().model_call(operation=..., provider=...,
model=..., input_messages=...)` (all four keywords are required), recording
the response with `call.output(...)`. The subclass passes the harness's
`isinstance` check; each turn's span carries that turn's full message list, so
tool calls and simulated tool results are captured as messages. Token usage is
read off the recorded response's `usage` block (OpenAI, Anthropic, and Gemini
shapes); call `call.usage(input_tokens=..., output_tokens=...)` yourself only
when the harness returns a response without one. Leave a comment at the
subclass saying why the built-in integrations do not apply.

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
| Claude Agent SDK (`claude-agent-sdk`, `claude-code-sdk`) | `beaker-sdk[tracing,claude-agent-sdk]` | `claude_agent_sdk.registered(...)` scope, with its `options(...)`/`env(...)` passed to the query |
| Prime Intellect `verifiers` (`ToolEnv` / `StatefulToolEnv`, 0.3.x) | `beaker-sdk[tracing,verifiers]` | `verifiers.instrument(env)` on the environment instance, or a `verifiers.registered(env)` scope; **tool spans only** — model calls still need `trace.model_call(...)` |

`beaker trace instrument` detects the framework and installs its extras; it does
not replace the wiring guidance in this section. Install the framework extras
above rather than relying only on `beaker-sdk[tracing]`.

Every integration that attaches to a framework's telemetry takes the
application's existing telemetry through `existing=` and composes with it, so an
app's own OpenInference, LangSmith, or Logfire instrumentation keeps working; no
integration patches global state. (`verifiers` has no telemetry to compose with,
so its `instrument(...)` takes none.)

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

In the integration, pass `runtime.trace` instead of `current_trace()`. `config(...)`
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

The Claude Agent SDK produces no telemetry itself: it runs the Claude Code CLI
as a child process, and that CLI has its own OpenTelemetry instrumentation and
exports over OTLP to whatever endpoint its environment names. So the
integration does not instrument anything in Python — it opens an endpoint owned
by the capture and hands the child the environment that points at it. Pass the
result into the query instead of the application's options:

```python
from beaker.tracing import current_trace
from beaker.tracing.integrations import claude_agent_sdk as beaker_claude

async with beaker_claude.registered(current_trace()) as claude:
    async for message in query(prompt=prompt, options=claude.options(app_options)):
        handle(message)
```

`options(...)` returns a copy of the application's `ClaudeAgentOptions` with the
telemetry variables merged into its `env`; nothing is mutated, so the same
options object stays usable for queries made outside the capture. Use
`claude.env(existing=...)` instead when the application builds the child
environment itself. Both return the caller's values unchanged when no capture is
active, so they can be called unconditionally. With a long-lived
`ClaudeSDKClient`, keep the `registered(...)` scope open until the last
`receive_response()` is consumed, and `await claude.flush()` before leaving a
case — the CLI batches its exports, so telemetry still in flight when the
capture closes is recorded as an omission and downgrades the capture to
`incomplete`.

Content is opt-in in Claude Code and the integration asks for it, so prompts,
responses and tool input/output reach the capture for the optimizer to read.
When the repository must not archive that content, use
`registered(current_trace(), content=False)`: the receipt then reports absent
model input/output coverage, and only structure survives — the tree, timings,
tokens, model and tool names. Say so at handoff, because prompt optimization has
no prompts to read in that mode.

Use `with registered(current_trace()) as litellm_trace:` around synchronous
`completion(...)` calls and call `litellm_trace.wait()` before leaving the
case. An unflushed or unlogged call is dropped as a capture omission and
downgrades the capture to `incomplete`; do not let the registration scope end
before `flush()` or `wait()`.

`verifiers` exports no telemetry and runs the agent's tools itself, so its
integration wraps the environment *instance* — never the class or the package:

```python
from beaker.tracing.integrations import verifiers as beaker_verifiers

env = beaker_verifiers.instrument(load_environment(...))
result = await env.run_rollout(rollout_input, client, model, sampling_args)
```

Every `env.call_tool(...)` becomes one `tool_call` span: tool name, call id,
the arguments the model sent, the tool message content, and the exception when
the tool raised (re-raised, so the model still sees the error message).
Arguments a `StatefulToolEnv` injects itself (`add_tool(..., args_to_skip=[...])`,
typically the hidden world state) are recorded by name only. Instrumenting the
same environment twice is a no-op, so a cached environment shared across cases
can be instrumented once; without a pinned `trace=` each call records under the
capture active when it runs. Use `registered(env)` when the instrumentation must
be undone after the block.

This integration is the one exception to the ownership rule above: it records
tools only. `verifiers` drives the model through its own client wrappers, so
keep the application's `trace.model_call(...)` around the client's request
method (a `verifiers` client subclass that delegates to the real client) or use
the provider adapter — do not drop it because the adapter is installed. `beaker
trace instrument --check` accordingly does not count a wired `verifiers` adapter
as model coverage. The v1 `verifiers.v1.Toolset` API is not covered.

For frameworks absent from the list above — including provider SDKs (the
Anthropic SDK itself, not the Claude Agent SDK above) and LlamaIndex today —
wrap the real model call with `trace.model_call(...)`.
Wrap nested calls the same way, inside the enclosing operation, so they are
recorded as its child spans. Otherwise the capture can contain stages but zero
model calls, causing `beaker trace doctor --require-model-calls` to fail.

Prefer wrapping the real call, not the framework client. A transparent wrapper
that delegates through `__getattr__` can preserve behavior but still fail a
framework that validates clients with `isinstance(...)` or its own resolver.
When such a wrapper is unavoidable, make it a framework-specific adapter: it
must subclass the public client base the framework accepts, initialize that
base correctly, and delegate every required native conversion, lifecycle, and
request method to the real client. Put `trace.model_call(...)` around the
delegated request method only.

Before a hosted baseline, create the wrapped client locally and pass it through
the exact resolver or type check the application uses. Only execute the traced
call after that preflight succeeds. This catches an incompatible wrapper before
every hosted case becomes an unresolved rollout; do not assume a generic Beaker
proxy can satisfy another framework's client contract.

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
workflow agent inside `Integration.run_case`, including its sub-agents, tools,
retrievers, and nested model calls. A capture containing only judge or scorer
calls does not satisfy runtime trace validation.

Validate both the default-model branch and selected-model branch
through the existing application/evaluation path when feasible. Fail setup
clearly if `runtime.model` is present but the selected client cannot be
injected. Do not add tests for this validation.
