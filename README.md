# detra

LLM Guardrails & Observability -- pluggable backends, any-model evaluation.

detra evaluates LLM outputs against a YAML behavior spec, flags violations, and ships metrics to any telemetry backend. No vendor lock-in: swap the backend (Console, OpenTelemetry, Datadog) and the judge (GPT-4o, Claude, Gemini, Llama, ...) without changing application code.

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

@vg.trace("extract_entities")
async def extract_entities(doc: str):
    return await llm.complete(prompt)

result = await extract_entities("Contract text...")
# -> telemetry emitted, behaviors evaluated, flags raised if needed
```

## How It Works

```text
Your LLM function
       |
  @vg.trace()
       |
  +---------+     +-----------+     +------------------+
  | Measure  | --> | Evaluate  | --> | Emit telemetry   |
  | latency  |    | behaviors |     | via backend      |
  +---------+     +-----------+     +------------------+
                       |
                  Judge (any LLM)
                  checks expected/
                  unexpected behaviors
                  from YAML spec
```

1. **Decorator** wraps your function, measures latency.
2. **Evaluation engine** runs rule-based checks, then asks the configured **Judge** (any LLM) to assess output against the behavior spec.
3. **Backend** ships metrics, events, and flags to your telemetry system.

## Configuration

Create `detra.yaml`:

```yaml
app_name: my-llm-app
version: "1.0.0"
environment: production

# Backend: where telemetry goes (auto | console | otel | datadog)
backend: auto

# Judge: which LLM evaluates outputs
judge_config:
  provider: litellm          # or: gemini, none
  model: gpt-4o-mini         # any litellm-compatible model string
  temperature: 0.1

# Sampling: don't eval every request in prod
sampling:
  rate: 0.1                  # evaluate 10% of requests
  always_sample_errors: true

# Behavior spec per node
nodes:
  extract_entities:
    description: "Extract legal entities from documents"
    expected_behaviors:
      - "Must return valid JSON"
      - "Party names must come from the source document"
    unexpected_behaviors:
      - "Hallucinated party names"
      - "Fabricated dates not in source"
    adherence_threshold: 0.85
    security_checks:
      - pii_detection
      - prompt_injection

  summarize_document:
    description: "Summarize legal documents"
    expected_behaviors:
      - "Summary captures key terms and obligations"
      - "Preserves factual accuracy"
    unexpected_behaviors:
      - "Includes information not in the original document"
    adherence_threshold: 0.80

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

Judges are the LLMs that evaluate your app's outputs against the behavior spec.

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
2. **Security scans** (LLM-assisted): PII detection, prompt injection
3. **Behavior evaluation** (LLM judge): checks expected/unexpected behaviors from YAML spec
4. **Flagging**: automatic when score < threshold or security issues found
5. **Telemetry**: metrics, events, and flag alerts shipped via backend

### Manual evaluation

```python
result = await vg.evaluate(
    node_name="extract_entities",
    input_data="Contract text...",
    output_data={"entities": [...]},
)
print(f"Score: {result.score}, Flagged: {result.flagged}")
```

### Evaluation result fields

- `score` -- adherence score (0.0 to 1.0)
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
