"""Dashboard creation and management for detra."""

from detra.dashboard.templates import get_dashboard_definition
from detra.dashboard.builder import DashboardBuilder, WidgetBuilder

__all__ = [
    "get_dashboard_definition",
    "DashboardBuilder",
    "WidgetBuilder",
]
