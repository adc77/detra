"""
Comprehensive dashboard template showing ALL detra features.

This dashboard includes:
- LLM monitoring (adherence, latency, tokens)
- Error tracking (error count, types, users affected)
- Agent monitoring (workflows, tools, decisions)
- Security (PII, injections)
- Optimization (DSPy metrics, root cause analyses)
- SLOs and monitor status

Total widgets: 25+
"""

from typing import Any, Dict

from detra.dashboard.builder import WidgetBuilder


def get_comprehensive_dashboard(
    app_name: str,
    env: str = "production",
) -> Dict[str, Any]:
    """
    Get complete dashboard definition with ALL features.

    Args:
        app_name: Application name.
        env: Environment.

    Returns:
        Complete dashboard JSON.
    """
    dashboard = {
        "title": f"detra: {app_name} - Complete Observability",
        "description": "Comprehensive monitoring: LLM + Errors + Agents + Security + Optimization",
        "layout_type": "ordered",
        "template_variables": [
            {"name": "env", "prefix": "env", "default": env},
            {"name": "node", "prefix": "node", "default": "*"},
        ],
        "widgets": [],
    }

    # ==========================================================================
    # SECTION 1: EXECUTIVE SUMMARY (4 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 📊 Executive Summary\nReal-time health across all monitoring layers",
            background_color="blue",
            font_size="16",
        )
    )

    # Row 1: Key metrics
    dashboard["widgets"].extend([
        WidgetBuilder.query_value(
            "LLM Adherence Score",
            "avg:detra.node.adherence_score{*}",
            conditional_formats=[
                {"comparator": ">=", "value": 0.85, "palette": "white_on_green"},
                {"comparator": ">=", "value": 0.70, "palette": "white_on_yellow"},
                {"comparator": "<", "value": 0.70, "palette": "white_on_red"},
            ],
        ),
        WidgetBuilder.query_value(
            "Error Rate",
            "sum:detra.errors.count{*}.as_rate()",
            unit="errors/min",
            precision=2,
        ),
        WidgetBuilder.query_value(
            "Active Workflows",
            "sum:detra.agent.workflow.steps{*}",
            aggregator="sum",
        ),
    ])

    # ==========================================================================
    # SECTION 2: LLM MONITORING (6 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 🤖 LLM Monitoring\nPrompt quality, adherence scoring, and hallucination detection",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Adherence trend over time
        WidgetBuilder.timeseries(
            "Adherence Score by Node",
            [{"q": "avg:detra.node.adherence_score{*} by {node}", "display_type": "line"}],
            markers=[
                {"value": "y = 0.85", "display_type": "warning dashed"},
                {"value": "y = 0.70", "display_type": "error dashed"},
            ],
            yaxis={"min": "0", "max": "1"},
        ),

        # Flag rate percentage
        WidgetBuilder.timeseries(
            "Flag Rate %",
            [{
                "q": "(sum:detra.node.flagged{*}.as_count() / sum:detra.node.calls{*}.as_count()) * 100",
                "display_type": "bars"
            }],
        ),

        # Flags by category
        WidgetBuilder.toplist(
            "Flags by Category",
            "sum:detra.node.flagged{*} by {category}.as_count()",
            palette="warm",
        ),

        # LLM call volume
        WidgetBuilder.timeseries(
            "LLM Calls by Node",
            [{"q": "sum:detra.node.calls{*} by {node}.as_count()", "display_type": "bars"}],
        ),

        # Latency distribution
        WidgetBuilder.timeseries(
            "Latency (P50, P95, P99)",
            [
                {"q": "p50:detra.node.latency_ms{*}", "display_type": "line"},
                {"q": "p95:detra.node.latency_ms{*}", "display_type": "line"},
                {"q": "p99:detra.node.latency_ms{*}", "display_type": "line"},
            ],
        ),

        # Token usage
        WidgetBuilder.timeseries(
            "Token Usage",
            [{"q": "sum:detra.eval.tokens_used{*}.as_count()", "display_type": "area"}],
        ),
    ])

    # ==========================================================================
    # SECTION 3: ERROR TRACKING (5 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 🐛 Error Tracking\nApplication errors with full context (Sentry-style)",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Error timeline
        WidgetBuilder.timeseries(
            "Errors Over Time",
            [{"q": "sum:detra.errors.count{*}.as_count()", "display_type": "bars"}],
        ),

        # Errors by type
        WidgetBuilder.toplist(
            "Top Error Types",
            "sum:detra.errors.count{*} by {exception_type}.as_count()",
            palette="warm",
        ),

        # Error rate
        WidgetBuilder.query_value(
            "Error Rate (per minute)",
            "sum:detra.errors.count{*}.as_rate()",
            precision=2,
        ),

        # Unique errors
        WidgetBuilder.query_value(
            "Unique Error Groups",
            "count_nonzero:detra.errors.count{*} by {error_id}",
        ),

        # Errors by severity
        WidgetBuilder.toplist(
            "Errors by Level",
            "sum:detra.errors.count{*} by {level}.as_count()",
        ),
    ])

    # ==========================================================================
    # SECTION 4: AGENT MONITORING (6 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 🤖 Agent Workflows\nMulti-step agent processes, tool calls, and decisions",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Workflow duration
        WidgetBuilder.timeseries(
            "Agent Workflow Duration",
            [
                {"q": "avg:detra.agent.workflow.duration_ms{*} by {agent}", "display_type": "line"},
            ],
        ),

        # Workflow steps
        WidgetBuilder.timeseries(
            "Steps per Workflow",
            [{"q": "avg:detra.agent.workflow.steps{*} by {agent}", "display_type": "bars"}],
        ),

        # Tool calls
        WidgetBuilder.timeseries(
            "Tool Calls per Workflow",
            [{"q": "avg:detra.agent.tool_calls{*} by {agent}", "display_type": "bars"}],
        ),

        # Workflow success rate
        WidgetBuilder.query_value(
            "Workflow Success Rate",
            "(sum:detra.agent.workflow.completed{*} / sum:detra.agent.workflow.total{*}) * 100",
            unit="%",
        ),

        # Anomalies detected
        WidgetBuilder.timeseries(
            "Agent Anomalies Detected",
            [{"q": "sum:detra.agent.anomalies{*} by {anomaly_type}.as_count()", "display_type": "bars"}],
        ),

        # Active workflows gauge
        WidgetBuilder.query_value(
            "Active Workflows",
            "sum:detra.agent.workflow.active{*}",
        ),
    ])

    # ==========================================================================
    # SECTION 5: SECURITY MONITORING (4 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 🔒 Security Monitoring\nPII detection, prompt injection, and sensitive content",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # PII detections
        WidgetBuilder.timeseries(
            "PII Detections",
            [{"q": "sum:detra.security.pii_detected{*} by {type}.as_count()", "display_type": "bars"}],
        ),

        # Injection attempts
        WidgetBuilder.timeseries(
            "Prompt Injection Attempts",
            [{"q": "sum:detra.security.injection_attempts{*}.as_count()", "display_type": "area"}],
        ),

        # Security issues by severity
        WidgetBuilder.toplist(
            "Security Issues by Severity",
            "sum:detra.security.issues{*} by {severity}.as_count()",
            palette="warm",
        ),

        # Security event stream
        WidgetBuilder.event_stream(
            "Recent Security Events",
            "tags:source:detra tags:category:security",
            size="l",
        ),
    ])

    # ==========================================================================
    # SECTION 6: OPTIMIZATION & INTELLIGENCE (4 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## 🧠 Intelligence & Optimization\nDSPy prompt optimization and root cause analysis",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Prompts optimized
        WidgetBuilder.timeseries(
            "Prompts Optimized (DSPy)",
            [{"q": "sum:detra.optimization.prompts_optimized{*}.as_count()", "display_type": "bars"}],
        ),

        # Root cause analyses
        WidgetBuilder.timeseries(
            "Root Cause Analyses Performed",
            [{"q": "sum:detra.optimization.root_causes_analyzed{*}.as_count()", "display_type": "bars"}],
        ),

        # Optimization confidence
        WidgetBuilder.query_value(
            "Avg Optimization Confidence",
            "avg:detra.optimization.confidence{*}",
            precision=2,
        ),

        # Improvement success rate
        WidgetBuilder.query_value(
            "Optimization Success Rate",
            "(sum:detra.optimization.successful{*} / sum:detra.optimization.total{*}) * 100",
            unit="%",
        ),
    ])

    # ==========================================================================
    # SECTION 7: MONITORS & INCIDENTS (3 widgets)
    # ==========================================================================

    dashboard["widgets"].append(
        WidgetBuilder.note(
            "## ⚠️ Alerts & Incidents\nActive monitors and incident tracking",
            background_color="gray",
        )
    )

    dashboard["widgets"].extend([
        # Monitor summary
        WidgetBuilder.monitor_summary(
            "Monitor Status",
            "status:(alert OR warn OR no data) source:detra",
        ),

        # Incident timeline
        WidgetBuilder.event_stream(
            "Recent Incidents",
            "tags:source:detra tags:alert_type:error",
            size="l",
        ),

        # SLO status (if configured)
        WidgetBuilder.note(
            "**SLO Status**\n- Response Quality: 99.5% target\n- Latency: < 2s target\n- Error Rate: < 1% target",
        ),
    ])

    return dashboard


def get_widget_count() -> Dict[str, int]:
    """
    Get count of widgets by category.

    Returns:
        Dictionary with widget counts per section.
    """
    return {
        "executive_summary": 4,
        "llm_monitoring": 6,
        "error_tracking": 5,
        "agent_monitoring": 6,
        "security_monitoring": 4,
        "optimization": 4,
        "monitors_incidents": 3,
        "total": 32,
    }
