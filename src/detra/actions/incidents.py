"""Incident creation and management."""

from typing import Any, Optional

import structlog

from detra.actions.notifications import NotificationManager
from detra.evaluation.gemini_judge import EvaluationResult
from detra.telemetry.datadog_client import DatadogClient

logger = structlog.get_logger()


class IncidentManager:
    """
    Manages incident creation and escalation.

    Determines when to create incidents based on
    evaluation results and severity thresholds.
    """

    # Severity thresholds for automatic incident creation
    SEVERITY_THRESHOLDS = {
        "SEV-1": 0.3,   # Critical - immediate action required
        "SEV-2": 0.5,   # High - action required within 1 hour
        "SEV-3": 0.7,   # Medium - action required within 4 hours
        "SEV-4": 0.85,  # Low - action required within 24 hours
    }

    def __init__(
        self,
        datadog_client: DatadogClient,
        notification_manager: NotificationManager,
    ):
        """
        Initialize the incident manager.

        Args:
            datadog_client: Datadog client for incident creation.
            notification_manager: Notification manager for alerts.
        """
        self.datadog = datadog_client
        self.notifications = notification_manager
        self._created_incidents: list[dict[str, Any]] = []

    async def handle_flag(
        self,
        node_name: str,
        eval_result: EvaluationResult,
        input_data: Any = None,
        output_data: Any = None,
    ) -> Optional[dict[str, Any]]:
        """
        Handle a flagged evaluation result.

        Args:
            node_name: Name of the flagged node.
            eval_result: Evaluation result.
            input_data: Original input (for context).
            output_data: LLM output (for context).

        Returns:
            Incident info if created, None otherwise.
        """
        severity = self._determine_severity(eval_result)

        # Send notifications
        await self.notifications.notify_flag(
            node_name=node_name,
            score=eval_result.score,
            category=eval_result.flag_category or "unknown",
            reason=eval_result.flag_reason or "Unknown issue",
            details={
                "checks_failed": len(eval_result.checks_failed),
                "security_issues": len(eval_result.security_issues),
            },
        )

        # Create incident for severe issues
        if severity in ["SEV-1", "SEV-2"]:
            incident = await self._create_incident(
                node_name, eval_result, severity, input_data, output_data
            )
            return incident

        return None

    async def handle_security_issue(
        self,
        node_name: str,
        issue: dict[str, Any],
        input_data: Any = None,
        output_data: Any = None,
    ) -> Optional[dict[str, Any]]:
        """
        Handle a security issue detection.

        Args:
            node_name: Node where issue was detected.
            issue: Security issue details.
            input_data: Original input.
            output_data: LLM output.

        Returns:
            Incident info if created, None otherwise.
        """
        severity = issue.get("severity", "medium")

        if severity in ["critical", "high"]:
            # Always create incident for critical security issues
            title = f"Security Issue: {issue.get('check')} in {node_name}"

            incident = await self.datadog.create_incident(
                title=title,
                severity="SEV-1" if severity == "critical" else "SEV-2",
                customer_impacted=True,
            )

            if incident:
                self._created_incidents.append(incident)

                await self.notifications.notify_incident(
                    incident_id=incident["id"],
                    title=title,
                    severity="SEV-1" if severity == "critical" else "SEV-2",
                    details=issue,
                )

                logger.info(
                    "Security incident created",
                    incident_id=incident["id"],
                    node=node_name,
                    check=issue.get("check"),
                )

            return incident

        return None

    def _determine_severity(self, eval_result: EvaluationResult) -> str:
        """
        Determine incident severity from evaluation result.

        Args:
            eval_result: Evaluation result.

        Returns:
            Severity string (SEV-1 through SEV-4).
        """
        score = eval_result.score

        # Critical security issues always SEV-1
        critical_security = [
            i for i in eval_result.security_issues
            if i.get("severity") == "critical"
        ]
        if critical_security:
            return "SEV-1"

        # Determine by score
        for sev, threshold in self.SEVERITY_THRESHOLDS.items():
            if score < threshold:
                return sev

        return "SEV-4"

    async def _create_incident(
        self,
        node_name: str,
        eval_result: EvaluationResult,
        severity: str,
        input_data: Any,
        output_data: Any,
    ) -> Optional[dict[str, Any]]:
        """Create a Datadog incident."""
        title = f"LLM Adherence Issue: {node_name} - {eval_result.flag_category}"

        incident = await self.datadog.create_incident(
            title=title,
            severity=severity,
            customer_impacted=severity in ["SEV-1", "SEV-2"],
        )

        if incident:
            self._created_incidents.append(incident)

            await self.notifications.notify_incident(
                incident_id=incident["id"],
                title=title,
                severity=severity,
                details={
                    "node": node_name,
                    "score": eval_result.score,
                    "category": eval_result.flag_category,
                    "reason": eval_result.flag_reason,
                    "failed_checks": [c.behavior for c in eval_result.checks_failed],
                },
            )

            logger.info(
                "Incident created",
                incident_id=incident["id"],
                node=node_name,
                severity=severity,
            )

        return incident

    async def create_manual_incident(
        self,
        title: str,
        description: str,
        severity: str = "SEV-3",
        customer_impacted: bool = False,
        tags: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Create a manual incident.

        Args:
            title: Incident title.
            description: Incident description.
            severity: Severity level.
            customer_impacted: Whether customers are impacted.
            tags: Optional tags.

        Returns:
            Incident info if created, None otherwise.
        """
        incident = await self.datadog.create_incident(
            title=title,
            severity=severity,
            customer_impacted=customer_impacted,
        )

        if incident:
            self._created_incidents.append(incident)

            await self.notifications.notify_incident(
                incident_id=incident["id"],
                title=title,
                severity=severity,
                details={"description": description},
            )

        return incident

    def get_created_incidents(self) -> list[dict[str, Any]]:
        """Get list of incidents created in this session."""
        return self._created_incidents.copy()

    @staticmethod
    def should_create_incident(
        score: float,
        security_issues: list[dict[str, Any]],
        threshold: float = 0.5,
    ) -> bool:
        """
        Determine if an incident should be created.

        Args:
            score: Adherence score.
            security_issues: List of security issues.
            threshold: Score threshold for incident creation.

        Returns:
            True if incident should be created.
        """
        # Always create for critical security issues
        if any(i.get("severity") == "critical" for i in security_issues):
            return True

        # Create for low scores
        return score < threshold
