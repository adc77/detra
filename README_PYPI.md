# detra

**LLM Guardrails & Observability -- pluggable backends, any-model evaluation.**

detra evaluates LLM outputs against a YAML behavior spec, flags violations, and ships metrics to any telemetry backend. No vendor lock-in.

## Install

```bash
pip install detra                    # core only (6 deps)
pip install "detra[litellm]"         # + any-model judge
pip install "detra[otel]"            # + OpenTelemetry backend
pip install "detra[datadog]"         # + Datadog backend
pip install "detra[all]"             # everything
```

## Quick Start

```python
import detra

vg = detra.init("detra.yaml")

@vg.trace("extract_entities")
async def extract_entities(doc: str):
    result = await llm.complete(prompt)
    return result

# Tracing + evaluation happen automatically
result = await extract_entities("Contract text...")
```

## Define Behaviors in YAML

```yaml
app_name: my-llm-app

judge_config:
  provider: litellm
  model: gpt-4o-mini

sampling:
  rate: 0.1

nodes:
  extract_entities:
    expected_behaviors:
      - "Must return valid JSON"
      - "Party names must come from the source document"
    unexpected_behaviors:
      - "Hallucinated party names"
    adherence_threshold: 0.85
    security_checks:
      - pii_detection
      - prompt_injection
```

## Pluggable Architecture

**Backends** -- where telemetry goes:

| Backend | Install | Use case |
|---------|---------|----------|
| Console | included | Local dev, CI |
| OpenTelemetry | `detra[otel]` | Prometheus, Jaeger, OTLP |
| Datadog | `detra[datadog]` | Datadog LLM Observability |
| Custom | included | Implement the protocol |

**Judges** -- which LLM evaluates outputs:

| Judge | Install | Models |
|-------|---------|--------|
| LiteLLM | `detra[litellm]` | GPT-4o, Claude, Gemini, Llama, 100+ |
| Gemini | `detra[gemini]` | Google Gemini models |
| None | included | Rules-only mode |

## Evaluation Pipeline

1. **Rule checks** (fast): empty output, JSON validity, length
2. **Security scans**: PII, prompt injection (LLM-assisted)
3. **Behavior eval**: expected/unexpected behaviors from YAML spec
4. **Flag + alert**: when score < threshold or security issues found

## Decorator Types

```python
@vg.trace("node")          # generic
@vg.workflow("pipeline")   # workflow
@vg.llm("model_call")     # LLM call
@vg.task("processing")    # task
@vg.agent("step")         # agent
```

Works on sync and async functions. Safe inside running event loops (FastAPI, etc.).

## Links

- [GitHub](https://github.com/adc77/detra)
- [Examples](https://github.com/adc77/detra/tree/main/examples)

## License

MIT
