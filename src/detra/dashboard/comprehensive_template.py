"""
Comprehensive Detra Dashboard Template

Shows ALL observability features:
- LLM Monitoring (adherence, latency, flags)
- Error Tracking (counts, types, root causes)
- Agent Workflows (duration, steps, tool calls)
- Security (PII detection, injection attempts)
- DSPy Optimization (prompts improved, confidence)
- Actionable Insights (what to fix, recommendations)

Total widgets: 35+
"""

from typing import Any, Dict

from detra.dashboard.builder import WidgetBuilder


def get_comprehensive_dashboard(
    app_name: str,
    env: str = "production",
) -> Dict[str, Any]:
    """
    Generate comprehensive dashboard with all detra features.

    Args:
        app_name: Application name.
        env: Environment.

    Returns:
        Complete dashboard JSON definition.
    """
    dashboard = {
        "title": f"Detra: {app_name} - LLM Observability",
        "description": "Complete observability: LLM + Errors + Agents + Security + Optimization",
        "layout_type": "ordered",
        "template_variables": [
            {"name": "env", "prefix": "env", "default": env},
            {"name": "node", "prefix": "node", "default": "*"},
            {"name": "agent", "prefix": "agent", "default": "*"},
        ],
        "widgets": [],
    }

    # ==========================================================================
    # SECTION 1: EXECUTIVE SUMMARY (KPIs)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Executive Summary",
            background_color="vivid_blue",
        )
    )

    dashboard["widgets"].extend([
        WidgetBuilder.query_value(
            "LLM Adherence Score",
            "avg:detra.node.adherence_score{$env,$node}",
            conditional_formats=[
                {"comparator": ">=", "value": 0.85, "palette": "white_on_green"},
                {"comparator": ">=", "value": 0.70, "palette": "white_on_yellow"},
                {"comparator": "<", "value": 0.70, "palette": "white_on_red"},
            ],
        ),
        WidgetBuilder.query_value(
            "Error Count (24h)",
            "sum:detra.errors.count{$env}.as_count()",
            conditional_formats=[
                {"comparator": "<=", "value": 5, "palette": "white_on_green"},
                {"comparator": "<=", "value": 20, "palette": "white_on_yellow"},
                {"comparator": ">", "value": 20, "palette": "white_on_red"},
            ],
        ),
        WidgetBuilder.query_value(
            "Flag Rate",
            "(sum:detra.node.flagged{$env}.as_count() / sum:detra.node.calls{$env}.as_count()) * 100",
            unit="%",
            precision=1,
        ),
        WidgetBuilder.query_value(
            "Avg Latency",
            "avg:detra.node.latency{$env}",
            precision=0,
            unit="ms",
        ),
        WidgetBuilder.query_value(
            "Active Workflows",
            "sum:detra.agent.workflow.active{$env}",
        ),
        WidgetBuilder.query_value(
            "Security Issues",
            "sum:detra.security.issues{$env}.as_count()",
            conditional_formats=[
                {"comparator": "<=", "value": 0, "palette": "white_on_green"},
                {"comparator": ">", "value": 0, "palette": "white_on_red"},
            ],
        ),
    ])

    # ==========================================================================
    # SECTION 2: LLM MONITORING
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## LLM Monitoring\nPrompt adherence, hallucination detection, and output quality",
            background_color="blue",
        )
    )

    dashboard["widgets"].extend([
        # Adherence trend
        WidgetBuilder.timeseries(
            "Adherence Score by Node",
            [{"q": "avg:detra.node.adherence_score{$env} by {node}", "display_type": "line"}],
            markers=[
                {"value": "y = 0.85", "display_type": "warning dashed"},
                {"value": "y = 0.70", "display_type": "error dashed"},
            ],
            yaxis={"min": "0", "max": "1"},
        ),

        # Flag rate over time
        WidgetBuilder.timeseries(
            "Flag Rate Over Time",
            [{"q": "(sum:detra.node.flagged{$env}.as_count() / sum:detra.node.calls{$env}.as_count()) * 100", "display_type": "bars"}],
        ),

        # Flags by category
        WidgetBuilder.toplist(
            "Flags by Category",
            "sum:detra.node.flagged{$env} by {category}.as_count()",
            palette="warm",
        ),

        # Flags by node
        WidgetBuilder.toplist(
            "Flags by Node",
            "sum:detra.node.flagged{$env} by {node}.as_count()",
            palette="orange",
        ),

        # Call volume
        WidgetBuilder.timeseries(
            "LLM Calls by Node",
            [{"q": "sum:detra.node.calls{$env} by {node}.as_count()", "display_type": "bars"}],
        ),

        # Latency percentiles
        WidgetBuilder.timeseries(
            "Latency P50 / P95 / P99",
            [
                {"q": "p50:detra.node.latency{$env}", "display_type": "line"},
                {"q": "p95:detra.node.latency{$env}", "display_type": "line"},
                {"q": "p99:detra.node.latency{$env}", "display_type": "line"},
            ],
        ),

        # Token usage
        WidgetBuilder.timeseries(
            "Evaluation Token Usage",
            [{"q": "sum:detra.evaluation.tokens{$env}.as_count()", "display_type": "area"}],
        ),
    ])

    # ==========================================================================
    # SECTION 3: ERROR TRACKING
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Error Tracking\nApplication errors with root cause analysis",
            background_color="red",
        )
    )

    dashboard["widgets"].extend([
        # Error timeline
        WidgetBuilder.timeseries(
            "Errors Over Time",
            [{"q": "sum:detra.errors.count{$env}.as_count()", "display_type": "bars"}],
        ),

        # Top error types
        WidgetBuilder.toplist(
            "Top Error Types",
            "sum:detra.errors.count{$env} by {exception_type}.as_count()",
            palette="warm",
        ),

        # Unique errors
        WidgetBuilder.query_value(
            "Unique Error Groups",
            "sum:detra.errors.unique{$env}",
        ),

        # Errors by level
        WidgetBuilder.toplist(
            "Errors by Severity",
            "sum:detra.errors.count{$env} by {level}.as_count()",
            palette="semantic",
        ),

        # Error event stream
        WidgetBuilder.event_stream(
            "Recent Errors",
            "tags:source:detra tags:alert_type:error",
            size="l",
        ),
    ])

    # ==========================================================================
    # SECTION 4: AGENT WORKFLOWS
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Agent Workflows\nMulti-step processes, tool calls, and decisions",
            background_color="purple",
        )
    )

    dashboard["widgets"].extend([
        # Workflow duration
        WidgetBuilder.timeseries(
            "Workflow Duration by Agent",
            [{"q": "avg:detra.agent.workflow.duration_ms{$env} by {agent}", "display_type": "line"}],
        ),

        # Steps per workflow
        WidgetBuilder.timeseries(
            "Steps per Workflow",
            [{"q": "avg:detra.agent.workflow.steps{$env} by {agent}", "display_type": "bars"}],
        ),

        # Tool calls
        WidgetBuilder.timeseries(
            "Tool Calls per Workflow",
            [{"q": "avg:detra.agent.tool_calls{$env} by {agent}", "display_type": "bars"}],
        ),

        # Success rate
        WidgetBuilder.query_value(
            "Workflow Success Rate",
            "(sum:detra.agent.workflow.completed{$env} / (sum:detra.agent.workflow.completed{$env} + sum:detra.agent.workflow.failed{$env})) * 100",
            unit="%",
            precision=1,
        ),

        # Anomalies
        WidgetBuilder.timeseries(
            "Agent Anomalies",
            [{"q": "sum:detra.agent.anomalies{$env} by {anomaly_type}.as_count()", "display_type": "bars"}],
        ),

        # Tool latency
        WidgetBuilder.timeseries(
            "Tool Call Latency",
            [{"q": "avg:detra.agent.tool.latency_ms{$env} by {tool_name}", "display_type": "line"}],
        ),
    ])

    # ==========================================================================
    # SECTION 5: SECURITY
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Security Monitoring\nPII detection, prompt injection, sensitive content",
            background_color="orange",
        )
    )

    dashboard["widgets"].extend([
        # PII detections
        WidgetBuilder.timeseries(
            "PII Detections by Type",
            [{"q": "sum:detra.security.pii_detected{$env} by {pii_type}.as_count()", "display_type": "bars"}],
        ),

        # Injection attempts
        WidgetBuilder.timeseries(
            "Prompt Injection Attempts",
            [{"q": "sum:detra.security.injection_attempts{$env}.as_count()", "display_type": "area"}],
        ),

        # Security issues by severity
        WidgetBuilder.toplist(
            "Security by Severity",
            "sum:detra.security.issues{$env} by {severity}.as_count()",
            palette="warm",
        ),

        # Security by check type
        WidgetBuilder.toplist(
            "Security by Check",
            "sum:detra.security.issues{$env} by {check}.as_count()",
        ),
    ])

    # ==========================================================================
    # SECTION 6: DSPY OPTIMIZATION
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Prompt Optimization (DSPy)\nAutomatic prompt improvements and fixes",
            background_color="green",
        )
    )

    dashboard["widgets"].extend([
        # Prompts optimized
        WidgetBuilder.timeseries(
            "Prompts Optimized",
            [{"q": "sum:detra.optimization.prompts_optimized{$env}.as_count()", "display_type": "bars"}],
        ),

        # Optimization confidence
        WidgetBuilder.timeseries(
            "Optimization Confidence",
            [{"q": "avg:detra.optimization.confidence{$env}", "display_type": "line"}],
            yaxis={"min": "0", "max": "1"},
        ),

        # Root cause analyses
        WidgetBuilder.timeseries(
            "Root Cause Analyses",
            [{"q": "sum:detra.optimization.root_causes{$env}.as_count()", "display_type": "bars"}],
        ),

        # Success rate
        WidgetBuilder.query_value(
            "Optimization Success %",
            "(sum:detra.optimization.successful{$env} / sum:detra.optimization.total{$env}) * 100",
            unit="%",
        ),
    ])

    # ==========================================================================
    # SECTION 7: WHAT TO FIX (Actionable Insights)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## What to Fix\nActionable insights and recommendations",
            background_color="yellow",
        )
    )

    dashboard["widgets"].extend([
        # Nodes needing attention (low adherence)
        # Note: Shows highest adherence first (default toplist behavior)
        # Review the list to identify nodes with low scores
        WidgetBuilder.toplist(
            "Adherence by Node",
            "avg:detra.node.adherence_score{$env} by {node}",
            palette="warm",
            limit=10,
        ),

        # High flag rate nodes
        WidgetBuilder.toplist(
            "High Flag Rate Nodes",
            "(sum:detra.node.flagged{$env} by {node}.as_count() / sum:detra.node.calls{$env} by {node}.as_count()) * 100",
            palette="warm",
            limit=10,
        ),

        # Most common errors
        WidgetBuilder.toplist(
            "Most Frequent Errors",
            "sum:detra.errors.count{$env} by {exception_type}.as_count()",
            palette="red",
            limit=10,
        ),

        # Security hotspots
        WidgetBuilder.toplist(
            "Security Hotspots",
            "sum:detra.security.issues{$env} by {node}.as_count()",
            palette="orange",
            limit=5,
        ),

        # Slow nodes
        WidgetBuilder.toplist(
            "Slowest Nodes (P95)",
            "p95:detra.node.latency{$env} by {node}",
            limit=10,
        ),
    ])

    # ==========================================================================
    # SECTION 8: ALERTS & MONITORS
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## Alerts & Monitors\nActive alerts and incident status",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Monitor summary
        WidgetBuilder.monitor_summary(
            "Active Monitors",
            "tag:(source:detra)",
        ),

        # Recent events
        WidgetBuilder.event_stream(
            "Recent Events",
            "sources:detra",
            size="l",
        ),

        # SLO note
        WidgetBuilder.note(
            """### SLO Targets
- Adherence Score: > 0.85
- Error Rate: < 1%
- Latency P95: < 3000ms
- Security Issues: 0 critical""",
            background_color="white",
        ),
    ])

    return dashboard


def get_minimal_dashboard(app_name: str, env: str = "production") -> Dict[str, Any]:
    """
    Minimal dashboard with essential widgets only.

    Args:
        app_name: Application name.
        env: Environment.

    Returns:
        Minimal dashboard JSON.
    """
    return {
        "title": f"Detra: {app_name} (Minimal)",
        "description": "Essential LLM observability metrics",
        "layout_type": "ordered",
        "template_variables": [
            {"name": "env", "prefix": "env", "default": env},
        ],
        "widgets": [
            WidgetBuilder.query_value(
                "Adherence Score",
                "avg:detra.node.adherence_score{$env}",
                conditional_formats=[
                    {"comparator": ">=", "value": 0.85, "palette": "white_on_green"},
                    {"comparator": "<", "value": 0.85, "palette": "white_on_red"},
                ],
            ),
            WidgetBuilder.query_value(
                "Error Count",
                "sum:detra.errors.count{$env}.as_count()",
            ),
            WidgetBuilder.timeseries(
                "Adherence Over Time",
                [{"q": "avg:detra.node.adherence_score{$env}", "display_type": "line"}],
            ),
            WidgetBuilder.timeseries(
                "Errors Over Time",
                [{"q": "sum:detra.errors.count{$env}.as_count()", "display_type": "bars"}],
            ),
            WidgetBuilder.toplist(
                "Top Issues",
                "sum:detra.node.flagged{$env} by {category}.as_count()",
            ),
        ],
    }


def get_widget_count() -> Dict[str, int]:
    """Get widget counts by section."""
    return {
        "executive_summary": 6,
        "llm_monitoring": 7,
        "error_tracking": 5,
        "agent_workflows": 6,
        "security": 4,
        "dspy_optimization": 4,
        "what_to_fix": 5,
        "alerts_monitors": 3,
        "total": 40,
    }
