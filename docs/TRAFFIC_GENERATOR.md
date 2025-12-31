# Traffic Generator Documentation

## Overview

The `scripts/traffic_generator.py` script generates diverse HTTP traffic to the Legal AI Service to demonstrate and test all detra observability features. It sends various request types that trigger different monitoring scenarios, security checks, and optimization workflows.

## Purpose

The traffic generator is designed to:

1. **Test Normal Operations**: Generate standard LLM requests (entity extraction, summarization)
2. **Exercise Agent Workflows**: Test multi-step agent processes with and without web search
3. **Trigger Semantic Violations**: Send requests that may cause hallucinations or low adherence scores
4. **Test Security Features**: Send documents with PII and prompt injection attempts
5. **Simulate Errors**: Trigger various error types to test error tracking
6. **Test High Latency Scenarios**: Send large documents to test latency monitoring
7. **Trigger Optimization**: Send low-quality inputs to trigger DSPy prompt optimization and root cause analysis

## Request Types

The traffic generator sends 10 different request types with the following distribution:

| Request Type | Probability | Description |
|-------------|-------------|-------------|
| `normal_llm` | 25% | Standard entity extraction or summarization requests |
| `agent_workflow` | 15% | Full agent workflow with query (no search) |
| `with_search` | 10% | Agent workflow with web search enabled |
| `semantic_violation` | 10% | Vague documents that may trigger hallucinations |
| `low_score_trigger` | 10% | Documents designed to trigger low adherence scores (< 0.7) |
| `pii_exposure` | 8% | Documents containing PII (SSN, email, phone, credit card) |
| `injection_attempt` | 8% | Prompt injection attempts to test security |
| `error_trigger` | 8% | Requests that trigger ValueError, KeyError, or TypeError |
| `high_latency` | 6% | Large documents (3x normal size) to test latency monitoring |

## Usage

### Basic Usage

```bash
python3 scripts/traffic_generator.py --url http://localhost:8000 --requests 20 --delay 2
```

### Command Line Arguments

- `--url`: Service URL (default: `http://localhost:8000`)
- `--requests`: Number of requests to send (default: 50)
- `--delay`: Delay between requests in seconds (default: 2.0)
- `--batch`: Run in batch mode (multiple batches with delays)
- `--batch-size`: Requests per batch (default: 10)
- `--num-batches`: Number of batches (default: 5)
- `--batch-delay`: Delay between batches in seconds (default: 5.0)

### Batch Mode

For continuous load testing:

```bash
python3 scripts/traffic_generator.py --url http://localhost:8000 --batch --batch-size 10 --num-batches 5 --delay 1.0 --batch-delay 5.0
```

## What You'll See in Datadog Dashboard

After running the traffic generator, you'll see the following metrics and events in your Datadog dashboard:

### Core Metrics

#### Node-Level Metrics

- **`detra.node.latency`** (distribution)
  - Latency for each node operation
  - Tags: `node:{node_name}`, `span_kind:{workflow|llm|task|agent}`

- **`detra.node.calls`** (count)
  - Total number of node calls
  - Tags: `node:{node_name}`, `status:{success|error}`

- **`detra.node.adherence_score`** (gauge)
  - Adherence score (0.0 to 1.0) for each evaluation
  - Tags: `node:{node_name}`

- **`detra.node.flagged`** (count)
  - Count of flagged outputs (when score < threshold)
  - Tags: `node:{node_name}`, `category:{hallucination|format_error|security_issue|...}`

#### Evaluation Metrics

- **`detra.evaluation.latency`** (distribution)
  - Time taken for evaluation (rule checks + LLM evaluation)
  - Tags: `node:{node_name}`

- **`detra.evaluation.tokens`** (count)
  - Tokens consumed during Gemini evaluation
  - Tags: `node:{node_name}`

#### Security Metrics

- **`detra.security.issues`** (count)
  - Count of security issues detected
  - Tags: `node:{node_name}`, `check:{pii_detection|prompt_injection|sensitive_content}`, `severity:{low|medium|high}`

#### Agent Workflow Metrics

- **`detra.agent.workflow.duration_ms`** (gauge)
  - Duration of agent workflows in milliseconds
  - Tags: `agent:{agent_name}`, `status:{completed|failed|timeout}`

- **`detra.agent.workflow.steps`** (gauge)
  - Number of steps in each workflow
  - Tags: `agent:{agent_name}`

- **`detra.agent.tool_calls`** (gauge)
  - Number of tool calls made during workflow
  - Tags: `agent:{agent_name}`

#### Error Tracking Metrics

- **`detra.errors.count`** (count)
  - Count of errors captured
  - Tags: `error_id:{error_id}`, `exception_type:{ValueError|KeyError|TypeError|...}`, `level:{error|warning|info}`

#### Optimization Metrics

- **`detra.optimization.prompts_optimized`** (count)
  - Number of prompts optimized by DSPy
  - Triggered when adherence score < 0.7

- **`detra.optimization.root_causes`** (count)
  - Number of root cause analyses performed
  - Triggered when adherence score < 0.8

- **`detra.optimization.confidence`** (gauge)
  - Confidence score of optimizations (0.0 to 1.0)

### Events

The traffic generator will also generate various events in Datadog:

1. **Flag Events**: When outputs are flagged (low adherence, security issues)
   - Alert type: `warning` or `error`
   - Contains: flag reason, category, adherence score

2. **Security Events**: When PII or prompt injection is detected
   - Alert type: `error`
   - Contains: detected patterns, severity, affected content

3. **Agent Workflow Events**: For each agent workflow completion
   - Alert type: `info` (completed) or `error` (failed)
   - Contains: workflow steps, tool calls, duration

4. **Error Events**: When exceptions are captured
   - Alert type: `error`
   - Contains: stack trace, error context, breadcrumbs

5. **Incident Events**: When critical issues trigger incident creation
   - Alert type: `error`
   - Contains: incident details, severity, affected nodes

### LLM Observability Traces

All requests are automatically traced and submitted to Datadog's LLM Observability platform, where you can see:

- Request/response pairs
- Token usage
- Model information
- Latency breakdown
- Evaluation results
- Security scan results

## Expected Output

### Console Output

The traffic generator prints real-time progress:

```
Detra Traffic Generator
Target: http://localhost:8000
Requests: 20, Delay: 2.0s
============================================================
Service healthy: {'status': 'healthy'}

[1/20] normal_llm... OK
[2/20] agent_workflow... OK
[3/20] pii_exposure... OK
[4/20] low_score_trigger... OK
...
```

### Summary Output

After completion, you'll see a summary:

```
============================================================
Traffic Generation Complete
============================================================
Total Requests: 20
  Success: 18
  Failed: 2

By Type:
  Normal LLM: 5
  Agent Workflow: 3
  With Search: 2
  Semantic Violation: 2
  Low Score Trigger: 2 (triggers DSPy/root cause)
  PII Exposure: 2
  Injection Attempt: 2
  Error Trigger: 1
  High Latency: 1

Check Datadog dashboard for:
  - detra.optimization.prompts_optimized (DSPy)
  - detra.optimization.root_causes (Root Cause Analysis)
  - detra.optimization.confidence (Optimization confidence)
```

## Dashboard Queries

Here are some useful Datadog queries to run after generating traffic:

### Adherence Score Over Time
```
avg:detra.node.adherence_score{*}
```

### Flag Rate
```
sum:detra.node.flagged{*}.as_count()
```

### Security Issues by Type
```
sum:detra.security.issues{*}.as_count() by {check}
```

### Agent Workflow Duration
```
avg:detra.agent.workflow.duration_ms{*} by {agent}
```

### Error Rate
```
sum:detra.errors.count{*}.as_count() by {exception_type}
```

### Optimization Activity
```
sum:detra.optimization.prompts_optimized{*}.as_count()
sum:detra.optimization.root_causes{*}.as_count()
avg:detra.optimization.confidence{*}
```

## Troubleshooting

### Service Not Available

If you see "Service not available", ensure:
1. The service is running: `python3 -m uvicorn examples.legal_analyzer.service:app --reload --port 8000`
2. The URL is correct (check port number)
3. Environment variables are set (DD_API_KEY, DD_APP_KEY, GOOGLE_API_KEY)

### No Metrics in Datadog

If metrics don't appear:
1. Verify Datadog API keys are correct
2. Check network connectivity to Datadog
3. Ensure detra is properly initialized in the service
4. Wait a few minutes for metrics to propagate

### High Failure Rate

Some failures are expected:
- Injection attempts may return 400 (security block)
- Error triggers intentionally cause errors
- Low score triggers may have lower success rates

Check the summary to see which request types are failing.

