"""Dashboard JSON templates for Datadog."""

from typing import Any


def get_dashboard_definition(app_name: str, env: str = "production") -> dict[str, Any]:
    """
    Generate the complete dashboard definition.

    Args:
        app_name: Application name for the dashboard.
        env: Environment (development, staging, production).

    Returns:
        Complete dashboard JSON definition.
    """
    return {
        "title": f"VertiGuard: {app_name} LLM Observability",
        "description": "End-to-end LLM observability dashboard with health metrics, security signals, and actionable insights",
        "widgets": [
            # Row 1: Health Overview
            {
                "definition": {
                    "title": "Application Health",
                    "type": "group",
                    "layout_type": "ordered",
                    "widgets": [
                        {
                            "definition": {
                                "title": "Overall Adherence Score",
                                "type": "query_value",
                                "requests": [
                                    {
                                        "q": "avg:vertiguard.node.adherence_score{*}",
                                        "aggregator": "avg",
                                    }
                                ],
                                "precision": 2,
                                "custom_unit": "",
                                "conditional_formats": [
                                    {"comparator": ">=", "value": 0.85, "palette": "white_on_green"},
                                    {"comparator": ">=", "value": 0.70, "palette": "white_on_yellow"},
                                    {"comparator": "<", "value": 0.70, "palette": "white_on_red"},
                                ],
                            }
                        },
                        {
                            "definition": {
                                "title": "Flag Rate (5m)",
                                "type": "query_value",
                                "requests": [
                                    {
                                        "q": "sum:vertiguard.node.flagged{*}.as_count() / sum:vertiguard.node.calls{*}.as_count() * 100",
                                        "aggregator": "avg",
                                    }
                                ],
                                "precision": 1,
                                "custom_unit": "%",
                                "conditional_formats": [
                                    {"comparator": "<=", "value": 5, "palette": "white_on_green"},
                                    {"comparator": "<=", "value": 15, "palette": "white_on_yellow"},
                                    {"comparator": ">", "value": 15, "palette": "white_on_red"},
                                ],
                            }
                        },
                        {
                            "definition": {
                                "title": "Error Rate (5m)",
                                "type": "query_value",
                                "requests": [
                                    {
                                        "q": "sum:vertiguard.node.calls{status:error}.as_count() / sum:vertiguard.node.calls{*}.as_count() * 100",
                                        "aggregator": "avg",
                                    }
                                ],
                                "precision": 1,
                                "custom_unit": "%",
                                "conditional_formats": [
                                    {"comparator": "<=", "value": 1, "palette": "white_on_green"},
                                    {"comparator": "<=", "value": 5, "palette": "white_on_yellow"},
                                    {"comparator": ">", "value": 5, "palette": "white_on_red"},
                                ],
                            }
                        },
                        {
                            "definition": {
                                "title": "Avg Latency",
                                "type": "query_value",
                                "requests": [
                                    {
                                        "q": "avg:vertiguard.node.latency{*}",
                                        "aggregator": "avg",
                                    }
                                ],
                                "precision": 0,
                                "custom_unit": "ms",
                                "conditional_formats": [
                                    {"comparator": "<=", "value": 2000, "palette": "white_on_green"},
                                    {"comparator": "<=", "value": 5000, "palette": "white_on_yellow"},
                                    {"comparator": ">", "value": 5000, "palette": "white_on_red"},
                                ],
                            }
                        },
                    ],
                }
            },
            # Row 2: Adherence Trends
            {
                "definition": {
                    "title": "Adherence Score Over Time",
                    "type": "timeseries",
                    "requests": [
                        {
                            "q": "avg:vertiguard.node.adherence_score{*} by {node}",
                            "display_type": "line",
                        }
                    ],
                    "markers": [
                        {"value": "y = 0.85", "display_type": "warning dashed"},
                        {"value": "y = 0.70", "display_type": "error dashed"},
                    ],
                    "yaxis": {"min": "0", "max": "1"},
                }
            },
            # Row 3: Flag Analysis
            {
                "definition": {
                    "title": "Flags by Category",
                    "type": "toplist",
                    "requests": [
                        {
                            "q": "sum:vertiguard.node.flagged{*} by {category}.as_count()",
                            "style": {"palette": "warm"},
                        }
                    ],
                }
            },
            {
                "definition": {
                    "title": "Flags by Node",
                    "type": "toplist",
                    "requests": [
                        {
                            "q": "sum:vertiguard.node.flagged{*} by {node}.as_count()",
                            "style": {"palette": "orange"},
                        }
                    ],
                }
            },
            # Row 4: Security Signals
            {
                "definition": {
                    "title": "Security Signals",
                    "type": "group",
                    "layout_type": "ordered",
                    "widgets": [
                        {
                            "definition": {
                                "title": "Security Issues by Type",
                                "type": "toplist",
                                "requests": [
                                    {
                                        "q": "sum:vertiguard.security.issues{*} by {check}.as_count()",
                                        "style": {"palette": "red"},
                                    }
                                ],
                            }
                        },
                        {
                            "definition": {
                                "title": "Security Issues Over Time",
                                "type": "timeseries",
                                "requests": [
                                    {
                                        "q": "sum:vertiguard.security.issues{*} by {severity}.as_count()",
                                        "display_type": "bars",
                                    }
                                ],
                            }
                        },
                    ],
                }
            },
            # Row 5: Performance
            {
                "definition": {
                    "title": "Latency Distribution",
                    "type": "heatmap",
                    "requests": [{"q": "avg:vertiguard.node.latency{*} by {node}"}],
                }
            },
            {
                "definition": {
                    "title": "Latency Percentiles",
                    "type": "timeseries",
                    "requests": [
                        {"q": "p50:vertiguard.node.latency{*}", "display_type": "line"},
                        {"q": "p95:vertiguard.node.latency{*}", "display_type": "line"},
                        {"q": "p99:vertiguard.node.latency{*}", "display_type": "line"},
                    ],
                }
            },
            # Row 6: Token Usage & Costs
            {
                "definition": {
                    "title": "Evaluation Token Usage",
                    "type": "timeseries",
                    "requests": [
                        {
                            "q": "sum:vertiguard.evaluation.tokens{*}.as_count()",
                            "display_type": "bars",
                        }
                    ],
                }
            },
            # Row 7: Call Volume
            {
                "definition": {
                    "title": "Call Volume by Node",
                    "type": "timeseries",
                    "requests": [
                        {
                            "q": "sum:vertiguard.node.calls{*} by {node}.as_count()",
                            "display_type": "bars",
                        }
                    ],
                }
            },
            # Row 8: Events Stream
            {
                "definition": {
                    "title": "Recent Events",
                    "type": "event_stream",
                    "query": "sources:vertiguard",
                    "event_size": "s",
                }
            },
            # Row 9: Monitor Summary
            {
                "definition": {
                    "title": "Monitor Status",
                    "type": "manage_status",
                    "query": "tag:(source:vertiguard)",
                    "sort": "status,asc",
                    "display_format": "countsAndList",
                }
            },
        ],
        "template_variables": [
            {"name": "node", "prefix": "node", "default": "*"},
            {"name": "env", "prefix": "env", "default": env},
        ],
        "layout_type": "ordered",
        "notify_list": [],
        "reflow_type": "fixed",
    }


def get_minimal_dashboard_definition(app_name: str) -> dict[str, Any]:
    """
    Generate a minimal dashboard with essential widgets.

    Args:
        app_name: Application name.

    Returns:
        Minimal dashboard JSON definition.
    """
    return {
        "title": f"VertiGuard: {app_name} (Minimal)",
        "description": "Essential LLM observability metrics",
        "widgets": [
            {
                "definition": {
                    "title": "Adherence Score",
                    "type": "query_value",
                    "requests": [
                        {
                            "q": "avg:vertiguard.node.adherence_score{*}",
                            "aggregator": "avg",
                        }
                    ],
                    "precision": 2,
                }
            },
            {
                "definition": {
                    "title": "Adherence Over Time",
                    "type": "timeseries",
                    "requests": [
                        {
                            "q": "avg:vertiguard.node.adherence_score{*}",
                            "display_type": "line",
                        }
                    ],
                }
            },
            {
                "definition": {
                    "title": "Call Volume",
                    "type": "timeseries",
                    "requests": [
                        {
                            "q": "sum:vertiguard.node.calls{*}.as_count()",
                            "display_type": "bars",
                        }
                    ],
                }
            },
        ],
        "layout_type": "ordered",
    }
