# detra - New Features

## 🎯 **Complete Observability Solution**

detra is now a **comprehensive monitoring platform** that handles:

1. ✅ **Traditional Error Tracking** (like Sentry)
2. ✅ **LLM Monitoring** (prompt/output quality)
3. ✅ **Agent Behavior Tracking** (workflows, tools, decisions)

---

## 🚨 **Feature 1: Error Tracking (Sentry-Style)**

### What It Does
Tracks **ALL application errors**, not just LLM-related ones:
- Exception capture with full stack traces
- Error grouping and deduplication
- Breadcrumb tracking (events leading to error)
- User context association
- Automatic Datadog incident creation

### Usage Example

```python
import detra

vg = detra.init("detra.yaml")

# Set user context
vg.error_tracker.set_user(
    user_id="user_123",
    email="user@example.com"
)

# Add breadcrumbs (events)
vg.error_tracker.add_breadcrumb(
    message="User clicked checkout",
    category="user_action",
)

# Automatic error capture
try:
    risky_operation()
except Exception as e:
    error_id = vg.error_tracker.capture_exception(
        e,
        context={"order_id": "12345"},
        level="error",
        tags=["service:checkout"],
    )
    print(f"Error tracked: {error_id}")

# Or use context manager
with vg.error_tracker.capture():
    risky_operation()  # Automatically captured on error
```

### What Gets Tracked

#### Error Context
- Exception type and message
- Full stack trace with file:line:function
- Breadcrumbs (last 100 events)
- User info (ID, email, etc.)
- Environment (production, staging)
- Release version
- Custom tags and metadata

#### Error Grouping
Similar errors are grouped together (like Sentry):
```
ValueError: File not found: /tmp/abc123
ValueError: File not found: /tmp/xyz789
→ Grouped as same error (normalized message)
```

#### Datadog Integration
- Creates Datadog Event for each error
- Submits `detra.errors.count` metric
- Creates incidents for critical/repeated errors
- Full context in event description

### Error Summary

```python
# Get all errors
errors = vg.error_tracker.get_all_errors()

for error in errors:
    print(f"Error {error['error_id']}")
    print(f"  Count: {error['count']}")
    print(f"  Type: {error['exception_type']}")
    print(f"  First seen: {error['first_seen']}")
    print(f"  Users affected: {error['users_affected']}")
```

---

## 🤖 **Feature 2: Agent Behavior Monitoring**

### What It Does
Tracks **multi-step agent workflows** (ReAct, tool calls, decisions):
- Thought → Action → Observation loops
- Tool usage patterns
- Decision chains
- Workflow anomalies (infinite loops, too many tools, failures)

### Usage Example

```python
import detra

vg = detra.init("detra.yaml")

# Start tracking agent workflow
workflow_id = vg.agent_monitor.start_workflow(
    agent_name="customer_support_agent",
    metadata={"session_id": "abc123"}
)

# Track ReAct loop
vg.agent_monitor.track_thought(
    workflow_id,
    thought="User wants order status. Need to search orders database."
)

vg.agent_monitor.track_action(
    workflow_id,
    action="search_orders",
    action_input={"user_id": "123"}
)

vg.agent_monitor.track_observation(
    workflow_id,
    observation="Found 3 orders for user"
)

# Track tool calls
vg.agent_monitor.track_tool_call(
    workflow_id,
    tool_name="database_query",
    tool_input={"query": "SELECT * FROM orders"},
    tool_output=[{"order_id": "456"}],
    latency_ms=245.3
)

# Track decisions
vg.agent_monitor.track_decision(
    workflow_id,
    decision="use_refund_tool",
    rationale="Order was cancelled, refund needed",
    confidence=0.92
)

# Complete workflow
vg.agent_monitor.complete_workflow(
    workflow_id,
    final_output="Refund processed successfully"
)
```

### What Gets Tracked

#### Workflow Steps
Each workflow is a sequence of steps:
- **THOUGHT**: Agent's reasoning
- **ACTION**: What agent decides to do
- **OBSERVATION**: Result of action
- **TOOL_CALL**: Specific tool invocation
- **DECISION**: Agent's decision point
- **FINAL_ANSWER**: Final output

#### Workflow Metrics
- Total steps taken
- Number of tool calls
- Duration (ms)
- Tool call latency
- Tool success/failure rate

#### Anomaly Detection
Automatically detects:
- **Excessive steps** (possible infinite loop)
- **Too many tool calls** (inefficient agent)
- **Repeated tool failures** (broken tools)
- **Long-running workflows** (stuck agent)

### Datadog Integration
- `detra.agent.workflow.duration_ms` metric
- `detra.agent.workflow.steps` metric
- `detra.agent.tool_calls` metric
- Workflow completion events
- Anomaly alerts

---

## 📊 **Dashboard Additions**

New dashboard widgets for:

### Error Tracking
- **Error Rate Over Time**: Track application stability
- **Error Types**: Most common errors
- **Users Affected**: Impact analysis
- **Error Timeline**: When errors occur

### Agent Monitoring
- **Active Workflows**: Currently running agents
- **Workflow Duration**: P50, P95, P99
- **Tool Usage**: Most/least used tools
- **Tool Success Rate**: Reliability metrics
- **Anomaly Alerts**: Unusual agent behaviors

---

## 🎯 **Complete Monitoring Stack**

### Layer 1: Code Errors (NEW)
```python
try:
    database.connect()
except Exception as e:
    vg.error_tracker.capture_exception(e)
```

### Layer 2: LLM Monitoring (Existing)
```python
@vg.trace("extract_entities")
async def extract_entities(doc):
    return await llm.complete(prompt)
# Automatically: adherence scoring, PII detection, hallucination detection
```

### Layer 3: Agent Workflows (NEW)
```python
workflow_id = vg.agent_monitor.start_workflow("my_agent")
vg.agent_monitor.track_thought(workflow_id, "Need to fetch data")
vg.agent_monitor.track_tool_call(workflow_id, "database", input, output)
vg.agent_monitor.complete_workflow(workflow_id, final_answer)
```

### Layer 4: Root Cause Analysis (Existing)
```python
# Automatically analyzes errors and suggests fixes
analysis = await vg.root_cause_analyzer.analyze_error(exception, context)
# Returns: root cause, suggested fixes, files to check
```

---

## 📦 **New Modules**

### `detra/errors/`
- **`tracker.py`**: Main error tracking class
- **`context.py`**: Error context data structures
- **`grouper.py`**: Error grouping and deduplication

### `detra/agents/`
- **`monitor.py`**: Agent workflow monitoring
- **`workflow.py`**: Workflow graph and visualization
- **`tools.py`**: Tool usage analytics

---

## 🚀 **Quick Start**

### 1. Error Tracking Only
```python
import detra

vg = detra.init("detra.yaml")

# All your code
with vg.error_tracker.capture():
    run_application()
```

### 2. LLM Monitoring Only
```python
import detra

vg = detra.init("detra.yaml")

@vg.trace("llm_call")
async def my_llm_function():
    return await llm.complete(prompt)
```

### 3. Agent Monitoring Only
```python
import detra

vg = detra.init("detra.yaml")

workflow_id = vg.agent_monitor.start_workflow("my_agent")
# ... track steps ...
vg.agent_monitor.complete_workflow(workflow_id, output)
```

### 4. Everything Together
```python
import detra

vg = detra.init("detra.yaml")

# Track errors
with vg.error_tracker.capture():
    # Track agent workflow
    workflow_id = vg.agent_monitor.start_workflow("agent")

    # Track LLM calls within workflow
    @vg.trace("llm_call")
    async def call_llm():
        return await llm.complete(prompt)

    result = await call_llm()
    vg.agent_monitor.complete_workflow(workflow_id, result)
```

---

## 🎯 **Why This Matters for Challenge**

### Before (LLM-only monitoring):
```
Problem: "My LLM app crashed"
Traditional: "Error 500" ❌
detra (old): "Adherence score low" ✓
```

### After (Complete monitoring):
```
Problem: "My LLM agent crashed"
detra (new): "ValueError in database.py:45.
Agent made 15 tool calls (expected <10).
3 database connection failures.
Root cause: Connection pool exhausted.
Fix: Increase pool size in config/db.yaml" ✅✅✅
```

### Competitive Advantage
1. **Most comprehensive**: Tracks code + LLM + agents
2. **Sentry + Langsmith + Custom** in one library
3. **Actionable insights**: Not just "what happened" but "why + how to fix"
4. **Agent-aware**: First to monitor multi-step agent workflows

---

## 📈 **Metrics Summary**

### New Metrics Added

#### Error Tracking
- `detra.errors.count` - Total errors
- `detra.errors.unique` - Unique error types
- `detra.errors.by_type` - Errors by exception type

#### Agent Monitoring
- `detra.agent.workflow.duration_ms` - Workflow duration
- `detra.agent.workflow.steps` - Steps per workflow
- `detra.agent.tool_calls` - Tool call count
- `detra.agent.tool.latency_ms` - Tool latency
- `detra.agent.anomalies` - Detected anomalies

---

## 🎬 **Demo Script Update**

For your video, now you can show:

### Act 1: Traditional Error (30s)
```python
# Show code error being tracked
# Dashboard shows error with stack trace
# Incident created automatically
```

### Act 2: LLM Issue (30s)
```python
# Show low adherence score
# Root cause analysis explains why
# DSPy suggests improved prompt
```

### Act 3: Agent Behavior (30s)
```python
# Show agent workflow
# Tool calls visualized
# Anomaly detected (too many steps)
```

### Act 4: All Together (30s)
```python
# Show dashboard with all metrics
# One platform for everything
# Comprehensive observability
```

---

## 🔥 **Innovation Highlights for Judges**

1. **First complete observability for AI agents**
   - Not just LLM calls
   - Full agent workflows with decision chains

2. **Sentry + Langsmith + More in one library**
   - Error tracking: Check
   - LLM monitoring: Check
   - Agent workflows: Check (unique!)

3. **Actionable intelligence**
   - Root cause analysis
   - Suggested fixes
   - File references

4. **Drop-in integration**
   - Single decorator
   - Context managers
   - Zero config required

5. **Production-ready**
   - Error grouping
   - Breadcrumbs
   - Incident creation
   - Multi-channel alerts

---

**This makes detra the most comprehensive AI observability platform! 🚀**
