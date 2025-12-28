"""Detection rules and monitor management for detra."""

from detra.detection.monitors import MonitorManager, MonitorDefinition
from detra.detection.rules import DetectionRule, DetectionRuleEngine
from detra.detection.templates import MONITOR_TEMPLATES, get_monitor_template

__all__ = [
    "MonitorManager",
    "MonitorDefinition",
    "DetectionRule",
    "DetectionRuleEngine",
    "MONITOR_TEMPLATES",
    "get_monitor_template",
]
