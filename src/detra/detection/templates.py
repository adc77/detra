"""Monitor JSON templates for Datadog."""

from typing import Any, Optional

# Pre-defined monitor templates
MONITOR_TEMPLATES: dict[str, dict[str, Any]] = {
    "adherence_warning": {
        "name": "VertiGuard: Low Adherence Score Warning",
        "type": "metric alert",
        "query": "avg(last_5m):avg:vertiguard.node.adherence_score{{*}} < {threshold}",
        "message": """## Low Adherence Score Detected

The LLM output adherence score has dropped below the warning threshold.

**Current Score:** {{value}}
**Threshold:** {threshold}
**Node:** {{node.name}}

### Recommended Actions
1. Check recent traces in LLM Observability
2. Review flagged outputs for patterns
3. Consider prompt adjustments

@slack-{slack_channel}
""",
        "thresholds": {"critical": 0.85},
        "priority": 3,
    },
    "adherence_critical": {
        "name": "VertiGuard: Critical Adherence Score",
        "type": "metric alert",
        "query": "avg(last_5m):avg:vertiguard.node.adherence_score{{*}} < {threshold}",
        "message": """## Critical Adherence Score Alert

The LLM output adherence score has dropped to critical levels.

**Current Score:** {{value}}
**Threshold:** {threshold}

### Immediate Actions Required
1. Review recent LLM outputs immediately
2. Check for system issues
3. Consider rolling back recent prompt changes

@pagerduty @slack-{slack_channel}
""",
        "thresholds": {"critical": 0.70},
        "priority": 1,
    },
    "flag_rate": {
        "name": "VertiGuard: High Flag Rate",
        "type": "metric alert",
        "query": "sum(last_5m):sum:vertiguard.node.flagged{{*}}.as_count() / sum:vertiguard.node.calls{{*}}.as_count() > {threshold}",
        "message": """## High Flag Rate Detected

More than {threshold_pct}% of LLM calls are being flagged.

**Flag Rate:** {{value}}

### Investigation Steps
1. Check flag categories in dashboard
2. Identify patterns in failed checks
3. Review input data quality

@slack-{slack_channel}
""",
        "thresholds": {"critical": 0.10},
        "priority": 2,
    },
    "latency_warning": {
        "name": "VertiGuard: High Latency Warning",
        "type": "metric alert",
        "query": "avg(last_5m):avg:vertiguard.node.latency{{*}} > {threshold}",
        "message": """## High Latency Detected

LLM call latency has exceeded warning threshold.

**Current Latency:** {{value}}ms
**Threshold:** {threshold}ms

### Possible Causes
- LLM provider issues
- Complex prompts
- Network latency

@slack-{slack_channel}
""",
        "thresholds": {"critical": 3000},
        "priority": 3,
    },
    "latency_critical": {
        "name": "VertiGuard: Critical Latency",
        "type": "metric alert",
        "query": "avg(last_5m):avg:vertiguard.node.latency{{*}} > {threshold}",
        "message": """## Critical Latency Alert

LLM call latency has exceeded critical threshold.

**Current Latency:** {{value}}ms
**Threshold:** {threshold}ms

### Immediate Actions
1. Check LLM provider status
2. Review recent changes
3. Consider fallback options

@pagerduty @slack-{slack_channel}
""",
        "thresholds": {"critical": 10000},
        "priority": 1,
    },
    "error_rate": {
        "name": "VertiGuard: High Error Rate",
        "type": "metric alert",
        "query": "sum(last_5m):sum:vertiguard.node.calls{{status:error}}.as_count() / sum:vertiguard.node.calls{{*}}.as_count() > {threshold}",
        "message": """## High Error Rate Detected

LLM call error rate has exceeded threshold.

**Error Rate:** {{value}}
**Threshold:** {threshold}

### Investigation Steps
1. Check error logs
2. Review LLM provider status
3. Check input validation

@slack-{slack_channel}
""",
        "thresholds": {"critical": 0.05},
        "priority": 2,
    },
    "security_issues": {
        "name": "VertiGuard: Security Issues Detected",
        "type": "metric alert",
        "query": "sum(last_5m):sum:vertiguard.security.issues{{*}}.as_count() > 0",
        "message": """## Security Issues Detected

Security checks have flagged potential issues.

**Issues Count:** {{value}}
**Check:** {{check.name}}
**Severity:** {{severity.name}}

### Immediate Actions
1. Review flagged content
2. Check for PII exposure
3. Investigate prompt injection attempts

@pagerduty @slack-{slack_channel}
""",
        "thresholds": {"critical": 0},
        "priority": 1,
    },
    "token_usage": {
        "name": "VertiGuard: High Token Usage",
        "type": "metric alert",
        "query": "sum(last_1h):sum:vertiguard.evaluation.tokens{{*}}.as_count() > {threshold}",
        "message": """## High Token Usage Alert

Evaluation token usage has exceeded threshold.

**Tokens Used:** {{value}}
**Threshold:** {threshold}

### Cost Optimization
1. Review evaluation frequency
2. Consider caching
3. Optimize prompts

@slack-{slack_channel}
""",
        "thresholds": {"critical": 50000},
        "priority": 4,
    },
}


def get_monitor_template(
    template_key: str,
    slack_channel: str = "llm-alerts",
    **params: Any,
) -> Optional[dict[str, Any]]:
    """
    Get a monitor template with parameters filled in.

    Args:
        template_key: Key of the template to use.
        slack_channel: Slack channel for notifications.
        **params: Additional parameters to fill in the template.

    Returns:
        Filled monitor template or None if template not found.
    """
    template = MONITOR_TEMPLATES.get(template_key)
    if not template:
        return None

    # Create a copy to avoid modifying the original
    result = template.copy()

    # Format query and message with parameters
    format_params = {"slack_channel": slack_channel, **params}

    if "query" in result:
        result["query"] = result["query"].format(**format_params)

    if "message" in result:
        result["message"] = result["message"].format(**format_params)

    # Update thresholds if threshold is provided
    if "threshold" in params and "thresholds" in result:
        result["thresholds"] = {
            k: params["threshold"] if k == "critical" else v
            for k, v in result["thresholds"].items()
        }

    return result


def generate_monitor_query(
    metric_name: str,
    aggregation: str = "avg",
    window: str = "last_5m",
    filter_tags: Optional[dict[str, str]] = None,
    comparison: str = "<",
    threshold: float = 0,
) -> str:
    """
    Generate a Datadog monitor query.

    Args:
        metric_name: Name of the metric.
        aggregation: Aggregation function (avg, sum, min, max).
        window: Time window.
        filter_tags: Tags to filter by.
        comparison: Comparison operator.
        threshold: Threshold value.

    Returns:
        Formatted monitor query.
    """
    # Build tag filter
    tag_filter = "*"
    if filter_tags:
        tag_parts = [f"{k}:{v}" for k, v in filter_tags.items()]
        tag_filter = ",".join(tag_parts)

    return f"{aggregation}({window}):{aggregation}:{metric_name}{{{tag_filter}}} {comparison} {threshold}"
