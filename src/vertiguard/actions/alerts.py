"""Alert handling and routing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

from vertiguard.actions.notifications import NotificationManager
from vertiguard.telemetry.events import EventSubmitter

logger = structlog.get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts."""
    FLAG = "flag"
    SECURITY = "security"
    ERROR = "error"
    LATENCY = "latency"
    THRESHOLD = "threshold"


@dataclass
class Alert:
    """Represents an alert to be processed."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    node_name: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class AlertHandler:
    """
    Handles alert processing and routing.

    Determines which notifications to send based on
    alert type and severity.
    """

    def __init__(
        self,
        notification_manager: NotificationManager,
        event_submitter: Optional[EventSubmitter] = None,
    ):
        """
        Initialize the alert handler.

        Args:
            notification_manager: Notification manager instance.
            event_submitter: Optional event submitter for Datadog events.
        """
        self.notifications = notification_manager
        self.events = event_submitter
        self._alert_count: dict[str, int] = {}
        self._suppressed_count: dict[str, int] = {}

    async def handle_alert(self, alert: Alert) -> bool:
        """
        Handle an alert by routing to appropriate channels.

        Args:
            alert: Alert to handle.

        Returns:
            True if alert was processed, False if suppressed.
        """
        # Check if alert should be suppressed
        if self._should_suppress(alert):
            self._suppressed_count[alert.alert_type.value] = (
                self._suppressed_count.get(alert.alert_type.value, 0) + 1
            )
            logger.debug("Alert suppressed", alert_type=alert.alert_type.value)
            return False

        # Update alert count
        self._alert_count[alert.alert_type.value] = (
            self._alert_count.get(alert.alert_type.value, 0) + 1
        )

        # Route based on type and severity
        await self._route_alert(alert)

        return True

    async def _route_alert(self, alert: Alert) -> None:
        """Route alert to appropriate channels."""
        # Always log
        log_method = logger.error if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH) else logger.warning
        log_method(
            f"Alert: {alert.title}",
            alert_type=alert.alert_type.value,
            severity=alert.severity.value,
            node=alert.node_name,
        )

        # Submit to Datadog events if available
        if self.events:
            await self._submit_event(alert)

        # Route based on alert type
        if alert.alert_type == AlertType.FLAG:
            await self._handle_flag_alert(alert)
        elif alert.alert_type == AlertType.SECURITY:
            await self._handle_security_alert(alert)
        elif alert.alert_type == AlertType.ERROR:
            await self._handle_error_alert(alert)
        elif alert.alert_type == AlertType.LATENCY:
            await self._handle_latency_alert(alert)

    async def _submit_event(self, alert: Alert) -> None:
        """Submit alert as Datadog event."""
        if not self.events:
            return

        alert_type_map = {
            AlertSeverity.CRITICAL: "error",
            AlertSeverity.HIGH: "error",
            AlertSeverity.MEDIUM: "warning",
            AlertSeverity.LOW: "info",
            AlertSeverity.INFO: "info",
        }

        await self.events.client.submit_event(
            title=alert.title,
            text=alert.message,
            alert_type=alert_type_map.get(alert.severity, "info"),
            tags=[
                f"alert_type:{alert.alert_type.value}",
                f"severity:{alert.severity.value}",
            ] + (alert.tags or []),
            aggregation_key=f"vertiguard-alert-{alert.alert_type.value}",
        )

    async def _handle_flag_alert(self, alert: Alert) -> None:
        """Handle flag-type alerts."""
        score = alert.details.get("score", 0.5)
        category = alert.details.get("category", "unknown")
        reason = alert.details.get("reason", alert.message)

        await self.notifications.notify_flag(
            node_name=alert.node_name or "unknown",
            score=score,
            category=category,
            reason=reason,
            details=alert.details,
        )

    async def _handle_security_alert(self, alert: Alert) -> None:
        """Handle security-type alerts."""
        check_type = alert.details.get("check_type", "unknown")

        await self.notifications.notify_security(
            node_name=alert.node_name or "unknown",
            check_type=check_type,
            severity=alert.severity.value,
            details=alert.message,
        )

    async def _handle_error_alert(self, alert: Alert) -> None:
        """Handle error-type alerts."""
        # For errors, we primarily log and submit to Datadog
        # Additional routing could be added here
        pass

    async def _handle_latency_alert(self, alert: Alert) -> None:
        """Handle latency-type alerts."""
        # Could add specific latency handling here
        pass

    def _should_suppress(self, alert: Alert) -> bool:
        """
        Check if an alert should be suppressed.

        Implements basic rate limiting.
        """
        # For now, no suppression
        # Could add rate limiting logic here
        return False

    def get_alert_counts(self) -> dict[str, int]:
        """Get counts of alerts by type."""
        return self._alert_count.copy()

    def get_suppressed_counts(self) -> dict[str, int]:
        """Get counts of suppressed alerts by type."""
        return self._suppressed_count.copy()

    def reset_counts(self) -> None:
        """Reset alert counts."""
        self._alert_count.clear()
        self._suppressed_count.clear()


async def create_flag_alert(
    node_name: str,
    score: float,
    category: str,
    reason: str,
) -> Alert:
    """
    Create a flag alert.

    Args:
        node_name: Name of the flagged node.
        score: Adherence score.
        category: Flag category.
        reason: Reason for flagging.

    Returns:
        Configured Alert instance.
    """
    severity = (
        AlertSeverity.CRITICAL if score < 0.3
        else AlertSeverity.HIGH if score < 0.5
        else AlertSeverity.MEDIUM if score < 0.7
        else AlertSeverity.LOW
    )

    return Alert(
        alert_type=AlertType.FLAG,
        severity=severity,
        title=f"Output flagged: {node_name}",
        message=reason,
        node_name=node_name,
        details={
            "score": score,
            "category": category,
            "reason": reason,
        },
        tags=[f"node:{node_name}", f"category:{category}"],
    )


async def create_security_alert(
    node_name: str,
    check_type: str,
    severity: str,
    details: str,
) -> Alert:
    """
    Create a security alert.

    Args:
        node_name: Node where issue was detected.
        check_type: Type of security check.
        severity: Issue severity.
        details: Issue details.

    Returns:
        Configured Alert instance.
    """
    severity_map = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.MEDIUM,
        "low": AlertSeverity.LOW,
    }

    return Alert(
        alert_type=AlertType.SECURITY,
        severity=severity_map.get(severity.lower(), AlertSeverity.MEDIUM),
        title=f"Security issue: {check_type}",
        message=details,
        node_name=node_name,
        details={
            "check_type": check_type,
            "severity": severity,
        },
        tags=[f"node:{node_name}", f"check:{check_type}"],
    )
