"""Detection rules and monitor management for VertiGuard."""

from vertiguard.detection.monitors import MonitorManager, MonitorDefinition
from vertiguard.detection.rules import DetectionRule, DetectionRuleEngine
from vertiguard.detection.templates import MONITOR_TEMPLATES, get_monitor_template

__all__ = [
    "MonitorManager",
    "MonitorDefinition",
    "DetectionRule",
    "DetectionRuleEngine",
    "MONITOR_TEMPLATES",
    "get_monitor_template",
]
