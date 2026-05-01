# detra

LLM/agent observability for behavior deviations, guardrails, and telemetry.

detra traces LLM and agent steps, compares outputs against configured behavior expectations, flags deviations, and ships metrics/events to your telemetry backend. It starts with deterministic checks and observability signals; LLM judges are optional and should be sampled or used with compact evidence.

## Install

```bash
pip install detra                    # core (6 deps, zero vendor lock-in)
pip install "detra[otel]"            # + OpenTelemetry backend
pip install "detra[datadog]"         # + Datadog backend
pip install "detra[litellm]"         # + any-model judge via litellm
pip install "detra[gemini]"          # + Gemini judge
pip install "detra[all]"             # everything
```

## 30-Second Quick Start

```python
import detra

vg = detra.init("detra.yaml")

@vg.trace("refund_policy_agent")
async def answer_refund_question(message: str):
    return await agent.run(message)

result = await answer_refund_question("Can I get a refund after 90 days?")
# -> latency, status, rule checks, deviation score, and flags are emitted
```

## How It Works

```text
Your LLM / agent step
       |
  @vg.trace()
       |
  +---------+     +---------------+     +------------------+
  | Trace   | --> | Check rules & | --> | Emit telemetry   |
  | runtime |     | deviations    |     | via backend      |
  +---------+     +---------------+     +------------------+
                         |
                  Optional sampled judge
                  for ambiguous behavior
```

1. **Decorator** wraps your function and captures latency, errors, input/output summaries, and node metadata.
2. **Evaluation engine** runs deterministic checks first, then computes behavior/deviation signals from your YAML spec.
3. **Optional Judge** can review sampled or ambiguous cases, ideally with compact evidence instead of full source context.
4. **Backend** ships metrics, events, and flags to your telemetry system.

## Configuration

Create `detra.yaml`:

```yaml
app_name: my-llm-app
version: "1.0.0"
environment: production

# Backend: where telemetry goes (auto | console | otel | datadog)
backend: auto

# Optional judge: use for sampled or ambiguous behavior checks
judge_config:
  provider: none             # or: litellm, gemini
  model: gpt-4o-mini
  temperature: 0.1

# Sampling: don't eval every request in prod
sampling:
  rate: 0.1                  # evaluate 10% of requests
  always_sample_errors: true

# Behavior/deviation spec per node
nodes:
  refund_policy_agent:
    description: "Answer refund questions from the approved policy"
    expected_behaviors:
      - "Must answer with either eligible, ineligible, or needs_review"
      - "Must mention the policy window when denying a refund"
      - "Must route to needs_review for missing order dates"
    unexpected_behaviors:
      - "Approves refunds outside the policy window"
      - "Invents policy exceptions"
      - "Asks for payment details"
    adherence_threshold: 0.90
    security_checks:
      - pii_detection
      - prompt_injection

  tool_router:
    description: "Choose the right tool for customer support requests"
    expected_behaviors:
      - "Must call lookup_order before giving order-specific answers"
      - "Must not call refund_payment without eligibility"
    unexpected_behaviors:
      - "Skips required lookup"
      - "Calls destructive tools without confirmation"
    adherence_threshold: 0.95

# Thresholds for alerting
thresholds:
  adherence_warning: 0.85
  adherence_critical: 0.70

# Security scanning
security:
  pii_detection_enabled: true
  prompt_injection_detection: true

# Notifications (optional)
integrations:
  slack:
    enabled: true
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#llm-alerts"
```

### Legacy Configs Still Work

If you have an existing config with `datadog:` and `gemini:` sections, detra auto-detects and uses them. No migration needed.

```yaml
# v0.1 style -- still works in v0.2
datadog:
  api_key: ${DD_API_KEY}
  app_key: ${DD_APP_KEY}
gemini:
  api_key: ${GOOGLE_API_KEY}
```

## Backends

Backends control where telemetry goes. All implement the same `TelemetryBackend` protocol.

| Backend | Install | Use case |
|---------|---------|----------|
| `ConsoleBackend` | included | Local dev, CI, debugging |
| `OTelBackend` | `detra[otel]` | Production with Prometheus, Jaeger, OTLP |
| `DatadogBackend` | `detra[datadog]` | Datadog LLM Observability |

### Auto-detection (default)

When `backend: auto` (the default), detra checks:
1. If valid Datadog API keys are present and `ddtrace` is installed -> Datadog
2. Otherwise -> Console

### Explicit backend

```yaml
backend: otel      # or: datadog, console
```

### Custom backend

Any object satisfying the protocol works:

```python
class MyBackend:
    async def emit_gauge(self, name, value, tags=None): ...
    async def emit_count(self, name, value, tags=None): ...
    async def emit_distribution(self, name, value, tags=None): ...
    async def emit_event(self, title, text, level="info", tags=None): ...
    async def flush(self): ...
    async def close(self): ...

vg = detra.init("detra.yaml", backend=MyBackend())
```

## Judges

Judges are optional LLM reviewers for behavior checks that deterministic rules cannot decide. Use them with sampling and compact evidence to avoid doubling production token cost.

| Judge | Install | Models |
|-------|---------|--------|
| `LiteLLMJudge` | `detra[litellm]` | GPT-4o, Claude, Gemini, Llama, Mistral, 100+ more |
| `GeminiJudge` | `detra[gemini]` | Gemini models via Google API |
| None | included | Rules-only mode (no LLM eval) |

### Via config

```yaml
judge_config:
  provider: litellm
  model: gpt-4o-mini
```

### Programmatic

```python
from detra.judges.litellm_judge import LiteLLMJudge

vg = detra.init("detra.yaml", judge=LiteLLMJudge("claude-sonnet-4-20250514"))
```

## Decorator Types

```python
@vg.trace("node_name")              # generic trace
@vg.workflow("pipeline_name")       # workflow/pipeline
@vg.llm("model_call")              # LLM call
@vg.task("data_processing")        # task
@vg.agent("agent_step")            # agent step
```

All decorators work on both sync and async functions. Sync functions called from inside an async context (e.g. FastAPI) are handled correctly.

### Options

```python
@vg.trace(
    "node_name",
    evaluate=True,            # run evaluation (default True)
    capture_input=True,       # capture function input
    capture_output=True,      # capture function output
    input_extractor=my_fn,    # custom input extraction
    output_extractor=my_fn,   # custom output extraction
)
```

## Evaluation Pipeline

1. **Rule-based checks** (fast, deterministic): empty output, JSON validity, length limits
2. **Security scans**: PII detection, prompt injection, sensitive content
3. **Behavior/deviation checks**: compare output against expected/unexpected behavior from YAML
4. **Optional sampled judge**: review ambiguous cases or compact evidence, not necessarily full inputs
5. **Flagging + telemetry**: emit scores, events, latency, and alerts via backend

### Manual evaluation

```python
result = await vg.evaluate(
    node_name="refund_policy_agent",
    input_data={"policy_window_days": 30, "order_age_days": 90},
    output_data={"decision": "eligible", "reason": "customer asked politely"},
)
print(f"Score: {result.score}, Flagged: {result.flagged}")
```

### Evaluation result fields

- `score` -- adherence/deviation score (0.0 to 1.0)
- `flagged` -- whether the output was flagged
- `flag_category` -- category (hallucination, format_error, etc.)
- `flag_reason` -- human-readable reason
- `checks_passed` / `checks_failed` -- individual behavior check results
- `security_issues` -- detected security issues
- `latency_ms` -- evaluation latency
- `eval_tokens_used` -- tokens consumed by the judge

## Metrics Emitted

All metrics are prefixed with `detra.` and tagged with `node` and `span_kind`.

| Metric | Type | Description |
|--------|------|-------------|
| `detra.node.latency_ms` | distribution | Function execution time |
| `detra.node.calls` | count | Call count (tagged with status) |
| `detra.eval.score` | gauge | Adherence score per evaluation |
| `detra.eval.flagged` | count | Flag events |
| `detra.eval.latency_ms` | distribution | Evaluation time |
| `detra.eval.tokens` | count | Tokens used by judge |

## Architecture

```text
src/detra/
├── __init__.py              # Public API
├── client.py                # Detra client, init(), resolution logic
├── backends/                # Pluggable telemetry backends
│   ├── base.py              # TelemetryBackend protocol
│   ├── console.py           # Stderr output (default)
│   ├── otel.py              # OpenTelemetry
│   └── datadog.py           # Datadog
├── judges/                  # Pluggable LLM judges
│   ├── base.py              # Judge protocol + result types
│   └── litellm_judge.py     # Any-model via litellm
├── config/                  # YAML + env var config
│   ├── schema.py            # Pydantic models
│   └── loader.py            # Loading + env expansion
├── decorators/              # @trace, @workflow, @llm, @task, @agent
│   └── trace.py             # Decorator implementation
├── evaluation/              # Evaluation pipeline
│   ├── engine.py            # Orchestrator
│   ├── gemini_judge.py      # Gemini judge (legacy)
│   ├── rules.py             # Rule-based checks
│   ├── classifiers.py       # Failure classification
│   └── prompts.py           # Prompt templates
├── security/                # PII, injection, content scanning
├── actions/                 # Alerts, notifications, incidents
├── telemetry/               # Datadog-specific (optional)
├── optimization/            # Root cause analysis, DSPy (optional)
└── utils/                   # Retry, serialization
```

## Dependency Profile

**Core** (always installed, ~6 packages):

| Package | Purpose |
|---------|---------|
| pydantic | Config validation |
| pydantic-settings | Env var config |
| pyyaml | YAML parsing |
| structlog | Structured logging |
| python-dotenv | .env file loading |
| httpx | HTTP client (webhooks) |

**Extras** (install only what you need):

| Extra | Packages | Purpose |
|-------|----------|---------|
| `otel` | opentelemetry-api, opentelemetry-sdk | OTel backend |
| `datadog` | ddtrace, datadog-api-client, datadog, certifi | DD backend |
| `gemini` | google-genai, tiktoken, tenacity | Gemini judge |
| `litellm` | litellm | Any-model judge |
| `optimization` | dspy-ai | Prompt optimization |
| `server` | fastapi, uvicorn | Example server |

## Testing

```bash
pip install -e ".[dev]"
pytest
pytest --cov=detra --cov-report=html
```

## Upgrading from v0.1

v0.2 is backward compatible. Your existing code and config files work without changes.

**What changed:**
- `import detra` no longer requires ddtrace or google-genai
- `detraConfig` still works (alias for `DetraConfig`)
- `detraTrace` still works (alias for `DetraTrace`)
- Old YAML configs with `datadog:` + `gemini:` sections auto-detect correctly
- Sync decorator no longer crashes inside running event loops

**New capabilities:**
- `backend: otel` / `backend: console` / `backend: datadog`
- `judge_config.provider: litellm` -- evaluate with any LLM
- `sampling.rate: 0.1` -- don't eval every request
- Custom backends and judges via Python protocols

## License

MIT
