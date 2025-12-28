# detra

End-to-end LLM Observability for Vertical AI Applications with Datadog Integration

detra is a comprehensive framework for monitoring, evaluating, and securing LLM applications. It provides automatic tracing, evaluation using Gemini, security scanning, alerting, and full integration with Datadog's LLM Observability platform.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Setup and Configuration](#setup-and-configuration)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [Code Structure](#code-structure)
- [Testing](#testing)
- [Example Application](#example-application)

## Overview

detra enables production-ready observability for LLM applications by:

- **Automatic Tracing**: Decorator-based tracing that captures inputs, outputs, and metadata
- **LLM Evaluation**: Gemini-powered evaluation to check adherence to expected behaviors
- **Security Scanning**: Detection of PII, prompt injection, and sensitive content
- **Alerting**: Integration with Slack, PagerDuty, and custom webhooks
- **Datadog Integration**: Full integration with Datadog LLM Observability, metrics, events, monitors, and dashboards
- **Incident Management**: Automatic incident creation for critical issues

## Key Features

### 1. Decorator-Based Tracing

Apply decorators to your LLM functions to automatically capture traces:

```python
import detra

vg = detra.init("detra.yaml")

@vg.trace("extract_entities")
async def extract_entities(document: str):
    return await llm.complete(prompt)
```

### 2. Behavior-Based Evaluation

Define expected and unexpected behaviors in configuration, and detra automatically evaluates outputs:

```yaml
nodes:
  extract_entities:
    expected_behaviors:
      - "Must return valid JSON"
      - "Party names must be from source document"
    unexpected_behaviors:
      - "Hallucinated party names"
      - "Fabricated dates"
    adherence_threshold: 0.85
```

### 3. Security Scanning

Automatic detection of:
- PII (emails, phone numbers, SSNs, credit cards)
- Prompt injection attempts
- Sensitive content (medical records, financial details)

### 4. Alerting and Notifications

Configure notifications via:
- Slack webhooks
- PagerDuty
- Custom webhooks

### 5. Datadog Integration

- Automatic submission to Datadog LLM Observability
- Custom metrics (latency, adherence scores, flags)
- Event creation for flags and errors
- Monitor creation for thresholds
- Dashboard generation

## Architecture

### Core Components

1. **Client (`client.py`)**: Main entry point that initializes all components
2. **Decorators (`decorators/trace.py`)**: Wraps functions with tracing and evaluation
3. **Evaluation Engine (`evaluation/engine.py`)**: Orchestrates rule-based and LLM-based evaluation
4. **Gemini Judge (`evaluation/gemini_judge.py`)**: Uses Gemini to evaluate behavior adherence
5. **Security Scanners (`security/scanners.py`)**: Detects PII, prompt injection, and sensitive content
6. **Datadog Client (`telemetry/datadog_client.py`)**: Handles all Datadog API interactions
7. **LLMObs Bridge (`telemetry/llmobs_bridge.py`)**: Bridges to Datadog's LLM Observability
8. **Notification Manager (`actions/notifications.py`)**: Handles Slack, PagerDuty, webhooks
9. **Incident Manager (`actions/incidents.py`)**: Creates and manages Datadog incidents
10. **Case Manager (`actions/cases.py`)**: Tracks issues that need investigation

### Evaluation Pipeline

1. **Rule-Based Checks**: Fast validation (JSON format, empty output, etc.)
2. **Security Scans**: PII detection, prompt injection scanning
3. **LLM Evaluation**: Gemini-based semantic evaluation of behaviors
4. **Flagging**: Automatic flagging when thresholds are breached
5. **Alerting**: Notifications sent based on severity

## Installation

### Prerequisites

- Datadog account with API key and Application key
- Google API key for Gemini evaluation (optional but recommended)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd detra

# Install dependencies
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### Dependencies

Core dependencies:
- `ddtrace>=2.10.0` - Datadog tracing
- `datadog-api-client>=2.20.0` - Datadog API client
- `google-genai>=0.2.0` - Gemini API
- `pydantic>=2.5.0` - Configuration validation
- `httpx>=0.26.0` - HTTP client for notifications
- `structlog>=24.1.0` - Structured logging

## Setup and Configuration

### 1. Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required: Datadog credentials
export DD_API_KEY=your_datadog_api_key
export DD_APP_KEY=your_datadog_app_key
export DD_SITE=datadoghq.com  # or your Datadog site

# Required: Google API key for evaluation
export GOOGLE_API_KEY=your_google_api_key

# Optional: Slack webhook
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export SLACK_CHANNEL=#llm-alerts

# Optional: PagerDuty
export PAGERDUTY_INTEGRATION_KEY=your_pagerduty_key
```

### 2. Configuration File

Create a `detra.yaml` configuration file:

```yaml
app_name: my-llm-app
version: "1.0.0"
environment: production

datadog:
  api_key: ${DD_API_KEY}
  app_key: ${DD_APP_KEY}
  site: ${DD_SITE}
  service: my-service
  env: production
  version: "1.0.0"

gemini:
  api_key: ${GOOGLE_API_KEY}
  model: gemini-2.5-flash
  temperature: 0.1
  max_tokens: 1024

nodes:
  extract_entities:
    description: "Extract entities from documents"
    expected_behaviors:
      - "Must return valid JSON"
      - "Must extract party names accurately"
    unexpected_behaviors:
      - "Hallucinated party names"
      - "Fabricated dates"
    adherence_threshold: 0.85
    latency_warning_ms: 2000
    latency_critical_ms: 5000
    security_checks:
      - pii_detection
      - prompt_injection
    tags:
      - "tier:critical"

thresholds:
  adherence_warning: 0.85
  adherence_critical: 0.70
  latency_warning_ms: 3000
  latency_critical_ms: 10000

security:
  pii_detection_enabled: true
  pii_patterns:
    - email
    - phone
    - ssn
    - credit_card
  prompt_injection_detection: true
  block_on_detection: false

integrations:
  slack:
    enabled: true
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#llm-alerts"
    notify_on:
      - flag_raised
      - incident_created
      - security_issue

create_dashboard: true
dashboard_name: "My LLM App - Observability"
```

### 3. Get API Keys

**Datadog:**
1. Go to https://app.datadoghq.com/organization-settings/api-keys
2. Create or copy your API key
3. Go to https://app.datadoghq.com/organization-settings/application-keys
4. Create or copy your Application key

**Google (Gemini):**
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key
3. Copy the key

## Quick Start

### 1. Basic Usage

```python
import detra

# Initialize detra
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

### 2. Setup Monitors and Dashboard

```python
# Create default monitors and dashboard
setup_results = await vg.setup_all(slack_channel="#llm-alerts")
print(f"Created {len(setup_results['monitors']['default_monitors'])} monitors")
print(f"Dashboard URL: {setup_results['dashboard']['url']}")
```

### 3. Manual Evaluation

```python
# Manually evaluate an output
result = await vg.evaluate(
    node_name="extract_entities",
    input_data="Document text",
    output_data={"entities": [...]},
)
print(f"Score: {result.score}, Flagged: {result.flagged}")
```

## Usage Guide

### Decorator Types

detra provides several decorator types:

```python
# Generic trace (default: workflow)
@vg.trace("node_name")

# Workflow trace
@vg.workflow("workflow_name")

# LLM call trace
@vg.llm("llm_call_name")

# Task trace
@vg.task("task_name")

# Agent trace
@vg.agent("agent_name")
```

### Decorator Options

```python
@vg.trace(
    "node_name",
    capture_input=True,      # Capture input data
    capture_output=True,     # Capture output data
    evaluate=True,           # Run evaluation
    input_extractor=custom_extractor,  # Custom input extraction
    output_extractor=custom_extractor, # Custom output extraction
)
```

### Module-Level Decorators

After initialization, you can use module-level decorators:

```python
import detra

vg = detra.init("detra.yaml")

@detra.trace("summarize")
async def summarize(text: str):
    return await llm.complete(prompt)
```

### Evaluation Results

Evaluation results include:

- `score`: Adherence score (0.0 to 1.0)
- `flagged`: Whether the output was flagged
- `flag_category`: Category of flag (hallucination, format_error, etc.)
- `flag_reason`: Reason for flagging
- `checks_passed`: List of passed behavior checks
- `checks_failed`: List of failed behavior checks
- `security_issues`: List of detected security issues
- `latency_ms`: Evaluation latency
- `eval_tokens_used`: Tokens used for evaluation

### Security Scanning

Security checks are automatically run when configured:

```yaml
nodes:
  my_node:
    security_checks:
      - pii_detection
      - prompt_injection
      - sensitive_content
```

Security issues are included in evaluation results and can trigger alerts.

### Alerting

Alerts are automatically sent based on:

- Flagged evaluations (below threshold)
- Security issues detected
- High latency
- Error rates

Configure in `detra.yaml`:

```yaml
integrations:
  slack:
    enabled: true
    webhook_url: ${SLACK_WEBHOOK_URL}
    notify_on:
      - flag_raised
      - incident_created
      - security_issue
    mention_on_critical:
      - "@here"
```

### Custom Monitors

Define custom monitors in configuration:

```yaml
alerts:
  - name: "High Hallucination Rate"
    description: "Too many outputs flagged for hallucination"
    metric: "detra.node.flagged"
    condition: "gt"
    threshold: 10
    window_minutes: 15
    severity: "warning"
    notify:
      - "@slack-llm-alerts"
    tags:
      - "category:hallucination"
```

## Code Structure

```
detra/
├── src/detra/
│   ├── __init__.py              # Main exports
│   ├── client.py                # detra client class
│   ├── actions/                 # Alerting and incident management
│   │   ├── alerts.py            # Alert handling
│   │   ├── cases.py             # Case management
│   │   ├── incidents.py         # Incident creation
│   │   └── notifications.py    # Slack, PagerDuty, webhooks
│   ├── config/                  # Configuration management
│   │   ├── schema.py            # Pydantic models
│   │   └── loader.py            # YAML loading and env expansion
│   ├── decorators/              # Tracing decorators
│   │   └── trace.py             # Main decorator implementation
│   ├── detection/               # Monitoring and detection
│   │   ├── monitors.py          # Datadog monitor creation
│   │   └── rules.py             # Rule-based checks
│   ├── evaluation/              # LLM evaluation
│   │   ├── engine.py            # Evaluation orchestrator
│   │   ├── gemini_judge.py      # Gemini-based evaluation
│   │   ├── classifiers.py       # Failure classification
│   │   ├── prompts.py           # Evaluation prompts
│   │   └── rules.py             # Rule-based evaluation
│   ├── security/                # Security scanning
│   │   ├── scanners.py          # PII, injection, content scanners
│   │   └── signals.py           # Security signal management
│   ├── telemetry/               # Datadog integration
│   │   ├── datadog_client.py    # Datadog API client
│   │   ├── llmobs_bridge.py     # LLM Observability bridge
│   │   ├── events.py            # Event submission
│   │   ├── logs.py              # Logging utilities
│   │   ├── metrics.py           # Metrics submission
│   │   └── traces.py            # Trace utilities
│   ├── dashboard/               # Dashboard creation
│   │   ├── builder.py           # Widget builders
│   │   └── templates.py         # Dashboard templates
│   └── utils/                   # Utilities
│       ├── retry.py             # Retry logic
│       └── serialization.py     # JSON utilities
├── examples/
│   └── legal_analyzer/          # Example application
│       ├── app.py               # Example code
│       └── detra.yaml      # Example config
├── tests/                       # Test suite
│   ├── test_actions.py          # Actions tests
│   ├── test_config.py           # Config tests
│   ├── test_evaluation.py       # Evaluation tests
│   ├── test_security.py         # Security tests
│   ├── test_telemetry.py        # Telemetry tests
│   └── test_utils.py            # Utils tests
└── pyproject.toml               # Project configuration
```

### Key Files Explained

**`client.py`**: Main entry point. The `detra` class initializes all components and provides the decorator methods.

**`decorators/trace.py`**: Implements the tracing decorator that wraps functions, captures I/O, runs evaluation, and submits telemetry.

**`evaluation/engine.py`**: Orchestrates the evaluation pipeline: rule checks → security scans → LLM evaluation.

**`evaluation/gemini_judge.py`**: Uses Gemini to evaluate outputs against expected/unexpected behaviors defined in config.

**`telemetry/datadog_client.py`**: Unified client for all Datadog API operations (metrics, events, monitors, dashboards, incidents).

**`telemetry/llmobs_bridge.py`**: Bridges to Datadog's LLM Observability platform for automatic trace submission.

**`security/scanners.py`**: Implements PII detection, prompt injection detection, and sensitive content scanning.

**`actions/notifications.py`**: Handles sending notifications to Slack, PagerDuty, and custom webhooks.

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=detra --cov-report=html

# Run specific test file
pytest tests/test_evaluation.py

# Run with verbose output
pytest -v

# Run async tests
pytest -v --asyncio-mode=auto
```

### Test Structure

Tests are organized by module:

- `test_actions.py`: Tests for alerting, cases, incidents, notifications
- `test_config.py`: Tests for configuration loading and validation
- `test_evaluation.py`: Tests for evaluation engine, Gemini judge, rule evaluator
- `test_security.py`: Tests for PII scanner, prompt injection scanner, content scanner
- `test_telemetry.py`: Tests for Datadog client, LLMObs bridge
- `test_utils.py`: Tests for retry logic, serialization utilities

### Test Configuration

Tests use fixtures defined in `conftest.py`:

- `sample_node_config`: Sample node configuration
- `sample_datadog_config`: Sample Datadog config
- `sample_gemini_config`: Sample Gemini config
- `sample_detra_config`: Complete detra config
- `mock_datadog_client`: Mocked Datadog client
- `mock_gemini_model`: Mocked Gemini model

### Writing Tests

Example test:

```python
import pytest
from detra import detra
from detra.config.schema import detraConfig, DatadogConfig, GeminiConfig

@pytest.mark.asyncio
async def test_evaluation():
    config = detraConfig(
        app_name="test",
        datadog=DatadogConfig(api_key="test", app_key="test"),
        gemini=GeminiConfig(api_key="test"),
    )
    vg = detra(config)
    
    result = await vg.evaluate(
        node_name="test_node",
        input_data="test input",
        output_data="test output",
    )
    
    assert 0 <= result.score <= 1
```

### Mocking External Services

Tests mock external services to avoid API calls:

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    with patch("detra.telemetry.datadog_client.MetricsApi") as mock_api:
        # Test code here
        pass
```

## Example Application

See `examples/legal_analyzer/` for a complete example application.

### Running the Example

```bash
cd examples/legal_analyzer

# Set environment variables
export DD_API_KEY=your_key
export DD_APP_KEY=your_key
export GOOGLE_API_KEY=your_key

# Run the demo
python app.py

# Or run in interactive mode
python app.py --interactive
```

The example demonstrates:
- Entity extraction from legal documents
- Document summarization
- Question answering with citations
- Full detra integration

## Advanced Usage

### Custom Input/Output Extractors

```python
def extract_input(args, kwargs):
    # Custom logic to extract input from function arguments
    return str(args[0])

def extract_output(output):
    # Custom logic to extract output
    return json.dumps(output)

@vg.trace(
    "my_node",
    input_extractor=extract_input,
    output_extractor=extract_output,
)
async def my_function(document: str):
    return await process(document)
```

### Disabling Evaluation

```python
@vg.trace("my_node", evaluate=False)
async def my_function():
    # Evaluation will be skipped
    return result
```

### Context in Evaluation

```python
result = await vg.evaluate(
    node_name="extract_entities",
    input_data=input,
    output_data=output,
    context={
        "document_type": "contract",
        "source": "legal_db",
    },
)
```

### Service Health Checks

```python
# Submit a health check
await vg.submit_service_check(
    status=0,  # 0=OK, 1=Warning, 2=Critical, 3=Unknown
    message="Service is healthy",
)
```

### Flushing Telemetry

```python
# Manually flush pending telemetry
vg.flush()
```

## Troubleshooting

### Common Issues

**1. "detra not initialized" error**
- Make sure to call `detra.init()` before using decorators
- Or use `detra.get_client()` after initialization

**2. Evaluation not running**
- Check that `evaluate=True` in decorator (default is True)
- Verify node configuration exists in `detra.yaml`
- Check that Gemini API key is set

**3. Datadog metrics not appearing**
- Verify `DD_API_KEY` and `DD_APP_KEY` are correct
- Check `DD_SITE` matches your Datadog site
- Ensure network connectivity to Datadog

**4. Notifications not sending**
- Verify webhook URLs are correct
- Check that integrations are enabled in config
- Review logs for error messages

### Debug Logging

Enable debug logging:

```python
import logging
import structlog

logging.basicConfig(level=logging.DEBUG)
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run tests: `pytest`
6. Submit a pull request

## License

[Add license information here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check the documentation
- Review example applications

