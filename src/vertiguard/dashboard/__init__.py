"""Dashboard creation and management for VertiGuard."""

from vertiguard.dashboard.templates import get_dashboard_definition
from vertiguard.dashboard.builder import DashboardBuilder, WidgetBuilder

__all__ = [
    "get_dashboard_definition",
    "DashboardBuilder",
    "WidgetBuilder",
]
