# detra

**End-to-end LLM Observability for Vertical AI Applications with Datadog Integration**

detra is a comprehensive Python framework for monitoring, evaluating, and securing LLM applications. It provides automatic tracing, Gemini-powered evaluation, security scanning, alerting, and full integration with Datadog's LLM Observability platform.

## Features

- **Automatic Tracing**: Decorator-based tracing that captures inputs, outputs, and metadata
- **LLM Evaluation**: Gemini-powered evaluation to check adherence to expected behaviors
- **Security Scanning**: Detection of PII, prompt injection, and sensitive content
- **Alerting**: Integration with Slack, PagerDuty, and custom webhooks
- **Datadog Integration**: Full integration with Datadog LLM Observability, metrics, events, monitors, and dashboards
- **Incident Management**: Automatic incident creation for critical issues

## Installation

```bash
pip install detra

# With optional dependencies
pip install detra[server]      # FastAPI/uvicorn support
pip install detra[dev]        # Development tools
pip install detra[optimization]  # DSPy optimization
pip install detra[all]        # All optional dependencies
```

## Quick Start

### 1. Install and Configure

```bash
# Install
pip install detra

# Set environment variables
export DD_API_KEY=your_datadog_api_key
export DD_APP_KEY=your_datadog_app_key
export GOOGLE_API_KEY=your_google_api_key
```

### 2. Create Configuration

Create `detra.yaml`:

```yaml
app_name: my-llm-app
datadog:
  api_key: ${DD_API_KEY}
  app_key: ${DD_APP_KEY}
  site: datadoghq.com
  service: my-service

gemini:
  api_key: ${GOOGLE_API_KEY}
  model: gemini-2.5-flash

nodes:
  extract_entities:
    expected_behaviors:
      - "Must return valid JSON"
      - "Must extract party names accurately"
    unexpected_behaviors:
      - "Hallucinated party names"
      - "Fabricated dates"
    adherence_threshold: 0.85
```

### 3. Use in Your Code

```python
import detra

# Initialize
vg = detra.init("detra.yaml")

# Decorate your LLM functions
@vg.trace("extract_entities")
async def extract_entities(document: str):
    # Your LLM call here
    result = await llm.complete(prompt)
    return result

# Use the function - tracing and evaluation happen automatically
result = await extract_entities("Contract text...")
```

### 4. Setup Monitoring

```python
# Create monitors and dashboard
setup_results = await vg.setup_all(slack_channel="#llm-alerts")
print(f"Dashboard URL: {setup_results['dashboard']['url']}")
```

## Usage Examples

### Basic Tracing

```python
import detra

vg = detra.init("detra.yaml")

@vg.trace("summarize")
async def summarize(text: str):
    return await llm.summarize(text)
```

### Different Trace Types

```python
@vg.workflow("document_processing")  # Workflow trace
@vg.llm("llm_call")                  # LLM call trace
@vg.task("data_extraction")         # Task trace
@vg.agent("agent_name")              # Agent trace
```

### Manual Evaluation

```python
result = await vg.evaluate(
    node_name="extract_entities",
    input_data="Document text",
    output_data={"entities": [...]},
)
print(f"Score: {result.score}, Flagged: {result.flagged}")
```

### Security Scanning

```yaml
nodes:
  my_node:
    security_checks:
      - pii_detection
      - prompt_injection
      - sensitive_content
```

### Alerting

```yaml
integrations:
  slack:
    enabled: true
    webhook_url: ${SLACK_WEBHOOK_URL}
    notify_on:
      - flag_raised
      - incident_created
      - security_issue
```

## Evaluation Pipeline

1. **Rule-Based Checks**: Fast validation (JSON format, empty output, etc.)
2. **Security Scans**: PII detection, prompt injection scanning
3. **LLM Evaluation**: Gemini-based semantic evaluation of behaviors
4. **Flagging**: Automatic flagging when thresholds are breached
5. **Alerting**: Notifications sent based on severity

## Requirements

- Datadog account with API key and Application key
- Google API key for Gemini evaluation (optional but recommended)

## Documentation

- **Github**: See [GitHub Repository](https://github.com/adc77/detra)
- **Examples**: [examples/](https://github.com/adc77/detra/tree/main/examples)

## License

MIT License
