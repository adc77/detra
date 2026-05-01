# detra

**LLM/agent observability for behavior deviations, guardrails, and telemetry.**

detra traces LLM and agent steps, compares outputs against configured behavior expectations, flags deviations, and ships metrics/events to your telemetry backend. Deterministic checks run first; LLM judges are optional and should be sampled or used with compact evidence.

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

@vg.trace("refund_policy_agent")
async def answer_refund_question(message: str):
    result = await agent.run(message)
    return result

# Tracing + deviation checks happen automatically
result = await answer_refund_question("Can I get a refund after 90 days?")
```

## Define Behaviors in YAML

```yaml
app_name: my-llm-app

judge_config:
  provider: none        # or: litellm, gemini
  model: gpt-4o-mini

sampling:
  rate: 0.1

nodes:
  refund_policy_agent:
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
```

## Pluggable Architecture

**Backends** -- where telemetry goes:

| Backend | Install | Use case |
|---------|---------|----------|
| Console | included | Local dev, CI |
| OpenTelemetry | `detra[otel]` | Prometheus, Jaeger, OTLP |
| Datadog | `detra[datadog]` | Datadog LLM Observability |
| Custom | included | Implement the protocol |

**Judges** -- optional reviewers for sampled or ambiguous behavior checks:

| Judge | Install | Models |
|-------|---------|--------|
| LiteLLM | `detra[litellm]` | GPT-4o, Claude, Gemini, Llama, 100+ |
| Gemini | `detra[gemini]` | Google Gemini models |
| None | included | Rules-only mode |

## Evaluation Pipeline

1. **Rule checks** (fast): empty output, JSON validity, length
2. **Security scans**: PII, prompt injection, sensitive content
3. **Behavior/deviation checks**: expected/unexpected behaviors from YAML spec
4. **Optional sampled judge**: for ambiguous cases or compact evidence
5. **Flag + alert**: when score < threshold or security issues found

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
