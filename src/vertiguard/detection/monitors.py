"""Monitor definitions and management."""

from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from vertiguard.config.schema import AlertConfig, ThresholdsConfig, VertiGuardConfig
from vertiguard.detection.templates import MONITOR_TEMPLATES, get_monitor_template
from vertiguard.telemetry.datadog_client import DatadogClient

logger = structlog.get_logger()


@dataclass
class MonitorDefinition:
    """Definition of a Datadog monitor."""
    name: str
    query: str
    message: str
    monitor_type: str = "metric alert"
    thresholds: dict[str, float] = field(default_factory=lambda: {"critical": 1})
    priority: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    notify: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "name": self.name,
            "type": self.monitor_type,
            "query": self.query,
            "message": self.message,
            "options": {
                "thresholds": self.thresholds,
                "priority": self.priority,
            },
            "tags": self.tags,
        }


class MonitorManager:
    """
    Manages Datadog monitors for VertiGuard.

    Handles creation, listing, and management of
    monitors based on configuration.
    """

    def __init__(self, datadog_client: DatadogClient, config: VertiGuardConfig):
        """
        Initialize the monitor manager.

        Args:
            datadog_client: Datadog client instance.
            config: VertiGuard configuration.
        """
        self.client = datadog_client
        self.config = config
        self.thresholds = config.thresholds
        self._created_monitors: dict[str, dict] = {}

    async def create_default_monitors(
        self, slack_channel: str = "llm-alerts"
    ) -> list[dict]:
        """
        Create all default monitors.

        Args:
            slack_channel: Slack channel for notifications.

        Returns:
            List of created monitor info dicts.
        """
        created = []

        monitors_to_create = [
            ("adherence_warning", {"threshold": self.thresholds.adherence_warning}),
            ("adherence_critical", {"threshold": self.thresholds.adherence_critical}),
            ("flag_rate", {"threshold": 0.10, "threshold_pct": 10}),
            ("latency_warning", {"threshold": self.thresholds.latency_warning_ms}),
            ("latency_critical", {"threshold": self.thresholds.latency_critical_ms}),
            ("error_rate", {"threshold": self.thresholds.error_rate_warning}),
            ("security_issues", {}),
            ("token_usage", {"threshold": self.thresholds.token_usage_warning}),
        ]

        for monitor_key, params in monitors_to_create:
            result = await self.create_monitor(monitor_key, slack_channel, **params)
            if result:
                created.append(result)
                self._created_monitors[monitor_key] = result

        logger.info(f"Created {len(created)} default monitors")
        return created

    async def create_monitor(
        self,
        monitor_key: str,
        slack_channel: str = "llm-alerts",
        **params: Any,
    ) -> Optional[dict]:
        """
        Create a monitor from template.

        Args:
            monitor_key: Key of the template to use.
            slack_channel: Slack channel for notifications.
            **params: Additional parameters for the template.

        Returns:
            Monitor info dict or None on failure.
        """
        template = get_monitor_template(monitor_key, slack_channel, **params)
        if not template:
            logger.error(f"Unknown monitor template: {monitor_key}")
            return None

        return await self.client.create_monitor(
            name=template["name"],
            query=template["query"],
            message=template["message"],
            monitor_type=template["type"],
            thresholds=template["thresholds"],
            priority=template.get("priority"),
            tags=[f"app:{self.config.app_name}", "source:vertiguard"],
        )

    async def create_custom_monitors(
        self, alerts: list[AlertConfig]
    ) -> list[dict]:
        """
        Create custom monitors from configuration.

        Args:
            alerts: List of alert configurations.

        Returns:
            List of created monitor info dicts.
        """
        created = []

        for alert in alerts:
            result = await self._create_from_alert_config(alert)
            if result:
                created.append(result)

        return created

    async def _create_from_alert_config(self, alert: AlertConfig) -> Optional[dict]:
        """Create a monitor from alert configuration."""
        condition_map = {
            "gt": ">",
            "lt": "<",
            "gte": ">=",
            "lte": "<=",
        }
        op = condition_map.get(alert.condition, ">")

        query = f"avg(last_{alert.window_minutes}m):avg:{alert.metric}{{*}} {op} {alert.threshold}"

        notify_str = " ".join(alert.notify)
        message = f"""## Custom Alert: {alert.name}

{alert.description}

**Current Value:** {{{{value}}}}
**Threshold:** {alert.threshold}

{notify_str}
"""

        return await self.client.create_monitor(
            name=f"VertiGuard: {alert.name}",
            query=query,
            message=message,
            thresholds={"critical": alert.threshold},
            tags=alert.tags + [f"app:{self.config.app_name}", "source:vertiguard"],
        )

    async def list_monitors(self) -> list[dict]:
        """List all VertiGuard monitors."""
        return await self.client.list_monitors(name_filter="VertiGuard:")

    async def create_monitor_from_definition(
        self, definition: MonitorDefinition
    ) -> Optional[dict]:
        """
        Create a monitor from a definition object.

        Args:
            definition: Monitor definition.

        Returns:
            Monitor info dict or None on failure.
        """
        return await self.client.create_monitor(
            name=definition.name,
            query=definition.query,
            message=definition.message,
            monitor_type=definition.monitor_type,
            thresholds=definition.thresholds,
            priority=definition.priority,
            tags=definition.tags,
        )

    def get_created_monitors(self) -> dict[str, dict]:
        """Get dictionary of monitors created in this session."""
        return self._created_monitors.copy()

    @staticmethod
    def build_custom_query(
        metric: str,
        aggregation: str = "avg",
        window_minutes: int = 5,
        tags: Optional[dict[str, str]] = None,
        comparison: str = ">",
        threshold: float = 0,
    ) -> str:
        """
        Build a custom monitor query.

        Args:
            metric: Metric name.
            aggregation: Aggregation function.
            window_minutes: Time window in minutes.
            tags: Tags to filter by.
            comparison: Comparison operator.
            threshold: Threshold value.

        Returns:
            Formatted query string.
        """
        tag_filter = "*"
        if tags:
            tag_parts = [f"{k}:{v}" for k, v in tags.items()]
            tag_filter = ",".join(tag_parts)

        return f"{aggregation}(last_{window_minutes}m):{aggregation}:{metric}{{{tag_filter}}} {comparison} {threshold}"
