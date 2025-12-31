"""Dashboard creation and management for detra."""

from detra.dashboard.comprehensive_template import (
    get_dashboard_definition,
    get_minimal_dashboard,
    get_widget_count,
)
from detra.dashboard.builder import DashboardBuilder, WidgetBuilder

__all__ = [
    "get_dashboard_definition",
    "get_minimal_dashboard",
    "get_widget_count",
    "DashboardBuilder",
    "WidgetBuilder",
]
