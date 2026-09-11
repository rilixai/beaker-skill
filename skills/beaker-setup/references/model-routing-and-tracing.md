# Model routing and tracing

## Choose routing during initial integration

Use this order for application calls during initial setup, unless the developer
explicitly chooses their own client and credentials:

1. **Automatic provider routing:** keep the existing client, provider URL, and
   request shape. Prefer supported hosted proxy calls using Beaker platform keys.
2. **Explicit gateway:** if the setup cannot use automatic routing and an
   OpenAI Chat Completions-compatible client is available, inject a Beaker
   gateway target through the existing evaluation interface when the SDK permits.
   This also uses platform credentials when no customer key is configured.
3. **Customer client and credentials:** use these when neither Beaker route can
   serve the call, or when the developer explicitly requests them.

Choose per call; a run can use more than one route. Do not copy local provider
keys into hosted settings merely because they exist. Preserve existing hosted
credential choices using the route-specific rules below, and explain which
credentials and billing each call will use.
Hosted judges have separate scorer-accounting requirements below.

This is a setup preference, not a retry chain. Surface authentication, budget,
and provider failures; do not switch routes to bypass them.

## Automatic provider routing

When provider routing is enabled for the hosted run, Beaker's sandbox proxy can
route the application's existing native clients without changing their base
URLs or request shapes. It works for production-model and prompt-only runs too;
it does not require `runtime.model`. Local execution outside the hosted sandbox
keeps the application's own routing and credentials.

The proxy handles these canonical provider hosts and inference endpoints:

| Provider host | Supported inference shape |
| --- | --- |
| `api.openai.com` | Chat Completions and Responses |
| `api.anthropic.com` | Messages |
| `generativelanguage.googleapis.com` | GenerateContent and StreamGenerateContent (`v1`/`v1beta`; streaming uses `alt=sse`) |
| `openrouter.ai` | Chat Completions |

Calls without a real provider key use platform credentials through Beaker and
are charged to the run; this proxy path does not look up organization keys.
A provider with a real key in the sandbox environment keeps its direct route;
a real key supplied by the client also uses direct provider billing.
Direct calls have no platform fallback. Preserve existing
customer keys and billing choices. Do not create keys solely to make supported
proxy calls work.

Keep `integrations.<id>.required_env` accurate when application code reads a
canonical provider-key variable. Before dispatch, Beaker fills declared canonical
variables from readable organization provider keys when no agent value is set.
Those real keys keep the direct route; they need not be duplicated as agent
secrets. Undeclared organization keys are not injected, so merely saving an
organization key does not change a keyless proxy call's platform billing.
With routing enabled, Beaker can satisfy a still-missing canonical key with a
non-secret placeholder. Other required credentials still need real values. Do
not add placeholders, host overrides, or certificate configuration yourself.

Confirm routing is enabled before relying on it. Platform routing covers
catalogued models and supported request capabilities, not every provider API.
Custom hosts, embeddings, Gemini's OpenAI-compatible path, and provider-hosted
tools can fall outside that support. The proxy handles HTTP/1.1 requests and SSE,
not arbitrary gRPC or WebSocket traffic. Assess the explicit gateway fallback
below before requesting customer credentials. Name any remaining unsupported
calls at handoff; do not silently change application behavior to fit a route.

Native Anthropic and Gemini routes retain native thinking settings, including
supported `budget_tokens` and `thinkingBudget` values. The Chat Completions
route accepts reasoning effort words rather than token budgets such as
`reasoning.max_tokens`. If an existing Chat Completions wrapper exposes a
budget, map it to a supported effort word in the evaluation adapter. Do not
apply that conversion to native requests merely because they are proxied.

## Explicit gateway fallback

When the setup cannot use automatic routing, prefer the gateway over requesting
customer credentials if a compatible Chat Completions client and the public SDK
can serve the call. For a selected model, `inference_target(runtime)` supplies
the run's `base_url`, `api_key`, and `model`. OpenAI Chat Completions clients and
compatible framework wrappers can use this path across supported providers.
Preserve client types and application behavior; check the model's capabilities.

The current helper requires both hosted credentials and `runtime.model`. If no
model is selected, keep the application's model defaults; do not invent a
comparison model or a private gateway URL to work around that requirement.
When this prevents the gateway fallback, report the SDK limitation before
falling back to customer credentials.

The gateway selects an agent key first, then an organization key, then a
platform key. With no customer key configured, this path needs no provider-key
setup and uses Beaker platform credentials. A configured but broken customer
key fails instead of falling through. Do not delete saved keys to force platform
billing; preserve the customer's existing choices.

The helper exposes Chat Completions, including SSE with `stream: true` and
`stream_options.include_usage`. Native proxy support does not make this helper
a Responses, Anthropic Messages, or Gemini endpoint. Do not rewrite a working
native call into the OpenAI shape merely to reach the gateway.

## Customer client and credentials

Use the customer's client and credentials as the last resort for unsupported
hosts, endpoints, models, or setup constraints, or honor an explicit request to
use them. Keep the existing provider API and client type. Declare the variables
the hosted application reads and configure evaluation-scoped values in hosted
settings; local shell and `.beaker/.env` values remain local. State why this
route is used and that its provider usage has no Beaker platform fallback.

## Model-selection boundary

Treat `runtime.model` as an explicit request for Beaker-controlled model
selection in the evaluation path. Its absence means use the application's
existing production-like client and model defaults. Hosted provider routing
can still supply transport and credentials for those calls.
`inference_target(runtime)` requires both a selected model and hosted run
credentials, and raises otherwise. Keep all Beaker imports for gateway
construction and routing decisions inside `.beaker/`.

The proxy forwards the model the application requests; it does not substitute
`runtime.model` or constrain native requests to the run's comparison targets.
Always wire the selected model through the application's existing injection
seam. For a native client, use its existing model override only when it can
represent the selected provider and model, and retain the native request shape.
If that client cannot run the requested model, report the limitation instead of
silently comparing repeated calls to the production model.

During initial setup, identify the optional model/client override and wire it
when a narrow injection seam exists. A compatible Chat Completions client can
use `inference_target(runtime)` for later comparisons; a native client can use
its supported model override. Keep the initial routing choice independent of
comparison readiness. Preparing an override does not select a comparison model
or authorize a comparison run.

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

Example gateway branch for a compatible client when the gateway fallback or
an explicit comparison needs it; the default branch keeps the application's
client and can use automatic routing:

```python
from beaker import CaseResult, inference_target

async def run_case(*, case_input, runtime):
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

`inference_target(runtime)` returns generic `base_url`, `api_key`, and `model` settings. `RolloutRuntime.model` contains the selected canonical `provider:model`; the helper does not invent a model when it is absent.

Remove a provider-key declaration only when no hosted path reads it, including
the production-model baseline, setup and scoring. Automatic proxy routing does
not make an application's environment-variable reads disappear. Never add
global environment-driven routing for Beaker.

For document integrations, also use the candidate documents or runtime object
provided through `runtime.targets_dir` or `runtime.candidate_runtime`.

## LLM-as-a-judge scoring

Configure a fixed `scorer_model` independently from the compared model. Pass it
per run with `--config '{"scorer_model":"openai:gpt-4.1-mini"}'`, or add a shared
default when every integration in the YAML uses the same judge:

```yaml
config_defaults:
  scorer_model: openai:gpt-4.1-mini
```

Only set this for an actual LLM judge and a developer-approved model; never
infer it from `runtime.model`. In `score_case`, use
`scoring_inference_target()` to obtain the dedicated hosted scorer gateway.
This accounts for judge traffic separately from candidate execution. In a hosted
run without `scorer_model`, it raises `RuntimeError("This run does not configure
a hosted LLM scorer model.")`; it does not fall back to the local judge.
Confirm the approved model is included in the actual launch configuration.
Smoke never executes `score_case`, so it cannot catch this missing configuration.
Deterministic scorers omit `scorer_model` and do not call this helper.

The `None` fallback requires all three: no scorer model, no usable scorer gateway
credentials, and no hosted run ID. In that local case, retain the application's
own judge client and credentials. Keep the same judge model in local evaluation.

A native judge call may also pass through the automatic proxy, but it is
recorded as `provider_proxy`, not `scorer`. The proxy neither identifies judge
calls nor applies `scorer_model`. Keep the dedicated scorer credential and
model wiring for hosted judge accounting. The scorer helper uses Chat
Completions; if an existing judge cannot use that shape without changing its
semantics, report the integration limitation rather than silently treating
automatic proxy billing as equivalent scorer accounting.

For the example YAML above, a task whose existing local judge uses the OpenAI
SDK can route its judge request as follows. Pass the task's established rubric
and answer in `question`, and convert the returned judgment into `CaseScore`
and per-criterion checks in async `score_case(*, case, result, case_files_dir)`.

```python
from openai import AsyncOpenAI
from beaker import scoring_inference_target

LOCAL_JUDGE_MODEL = "gpt-4.1-mini"  # Same judge as the run's scorer_model.

async def call_judge(question: str) -> str:
    target = scoring_inference_target()
    if target is None:
        client = AsyncOpenAI()  # Existing local provider configuration.
        model = LOCAL_JUDGE_MODEL
    else:
        client = AsyncOpenAI(base_url=target.base_url, api_key=target.api_key)
        model = target.model
    async with client:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
        )
        return response.choices[0].message.content or ""
```

For a different local provider, preserve the application's existing async judge
client and request shape in the local fallback; translate only provider-specific
model syntax. Hosted calls still use the dedicated scorer gateway. Keep
`score_case` non-blocking and close clients it owns on success or failure.
The selected integration's judge must remain the same across local evaluation,
the production-model baseline and every compared model.

When feasible, exercise both routes through an existing evaluation workflow:
with the hosted scorer target available, verify its URL, credentials and model
are used; without it, verify the local path still uses the agreed judge. Do not
print credentials or add consumer tests for this check. Structural smoke never
calls the scorer, so a passing smoke check does not verify judge routing.

Candidate tracing covers the application workflow, including nested model and
tool calls. Do not instrument scorer or judge calls as candidate activity.

## Trace evidence

Proxy usage and billing records do not replace a candidate trace. Keep framework
or call-site instrumentation for model inputs/outputs, tool executions, stages,
and parent/child relationships; a gateway usage record alone cannot validate
that coverage.

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

LLM-judge traffic must still declare launch `scorer_model` and use
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
around the call site. Do not put a transparent Python proxy, `__getattr__` forwarder,
or monkeypatched method in place of the client or model object. Client-type
checks reject such wrappers, and every case then fails before it runs.
Wrap the *call*, not the client, unless the framework requires a client wrapper
and the type-preserving adapter described below is necessary.

This restriction concerns Python client objects. Beaker's sandbox HTTP proxy
operates below those objects and does not replace their types or identities.

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
| Prime Intellect `verifiers` (`ToolEnv` / `StatefulToolEnv`, 0.3.x) | `beaker-sdk[tracing,verifiers]` | `verifiers.instrument(env)` on the environment instance; **tool spans only** — model calls still need `trace.model_call(...)` |

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
same environment twice with the same trace setting is a no-op, so a cached
environment shared across cases can be instrumented once. Without a pinned
`trace=`, each call records under the active capture and records nothing outside
a capture. Instrumentation lasts for the instance's lifetime; there is no undo
API. Use a separate evaluation instance if the application needs an untouched
environment afterward.

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
every hosted case becomes an unresolved rollout; do not assume a generic Python
client proxy can satisfy another framework's client contract.

First verify structural wiring with the real local dataset or the exact hosted
snapshot selected for launch:

```bash
beaker run smoke --strict --integration-id <id> --config '{"local_dataset_path":"<dataset-dir>"}'
beaker run smoke --strict --integration-id <id> --agent <selected-agent> --dataset <name@revision>
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
through the existing application/evaluation path when feasible. Check that the
selected model reaches the actual request; proxy success alone does not prove
that model selection or tracing works. Fail setup
clearly if `runtime.model` is present but the selected client cannot be
injected. Do not add tests for this validation.
