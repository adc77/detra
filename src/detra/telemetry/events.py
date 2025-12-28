"""Event submission utilities."""

from typing import Any, Optional

import structlog

from detra.telemetry.datadog_client import DatadogClient
from detra.utils.serialization import truncate_string

logger = structlog.get_logger()


class EventSubmitter:
    """
    High-level interface for submitting VertiGuard events.

    Provides semantic methods for common event types like
    flags, errors, and security issues.
    """

    def __init__(self, client: DatadogClient, app_name: str):
        """
        Initialize the event submitter.

        Args:
            client: Datadog client instance.
            app_name: Application name for tagging.
        """
        self.client = client
        self.app_name = app_name

    async def submit_flag_event(
        self,
        node_name: str,
        score: float,
        category: Optional[str],
        reason: Optional[str],
        failed_checks: Optional[list[str]] = None,
        input_preview: Optional[str] = None,
        output_preview: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Submit a flag event when output is flagged.

        Args:
            node_name: Name of the traced node.
            score: Adherence score.
            category: Flag category.
            reason: Reason for flagging.
            failed_checks: List of failed check descriptions.
            input_preview: Preview of input data.
            output_preview: Preview of output data.

        Returns:
            Event info dict or None on failure.
        """
        checks_text = ""
        if failed_checks:
            checks_text = "\n".join(f"- {check}" for check in failed_checks)

        text = f"""## Flag Details
- **Node:** {node_name}
- **Score:** {score:.2f}
- **Category:** {category or "unknown"}
- **Reason:** {reason or "No reason provided"}

## Failed Checks
{checks_text or "None recorded"}

## Input Preview
```
{truncate_string(input_preview or "N/A", 500)}
```

## Output Preview
```
{truncate_string(output_preview or "N/A", 500)}
```
"""

        alert_type = "warning" if score > 0.5 else "error"

        return await self.client.submit_event(
            title=f"VertiGuard Flag: {node_name}",
            text=text,
            alert_type=alert_type,
            tags=[
                f"node:{node_name}",
                f"category:{category or 'unknown'}",
                f"score:{score:.2f}",
                f"app:{self.app_name}",
            ],
            aggregation_key=f"vertiguard-flag-{node_name}",
        )

    async def submit_error_event(
        self,
        node_name: str,
        error: Exception,
        input_preview: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Submit an error event.

        Args:
            node_name: Name of the traced node.
            error: The exception that occurred.
            input_preview: Preview of input data.

        Returns:
            Event info dict or None on failure.
        """
        text = f"""## Error Details
- **Node:** {node_name}
- **Error Type:** {type(error).__name__}
- **Message:** {str(error)}

## Input Preview
```
{truncate_string(input_preview or "N/A", 300)}
```
"""

        return await self.client.submit_event(
            title=f"VertiGuard Error: {node_name}",
            text=text,
            alert_type="error",
            tags=[
                f"node:{node_name}",
                f"error_type:{type(error).__name__}",
                f"app:{self.app_name}",
            ],
            aggregation_key=f"vertiguard-error-{node_name}",
        )

    async def submit_security_event(
        self,
        node_name: str,
        check_type: str,
        severity: str,
        details: str,
        evidence: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Submit a security issue event.

        Args:
            node_name: Name of the traced node.
            check_type: Type of security check.
            severity: Issue severity.
            details: Issue details.
            evidence: Evidence of the issue.

        Returns:
            Event info dict or None on failure.
        """
        text = f"""## Security Issue Detected
- **Node:** {node_name}
- **Check Type:** {check_type}
- **Severity:** {severity}

## Details
{details}

## Evidence
```
{truncate_string(evidence or "N/A", 500)}
```
"""

        alert_type = "error" if severity in ("critical", "high") else "warning"

        return await self.client.submit_event(
            title=f"VertiGuard Security: {check_type} in {node_name}",
            text=text,
            alert_type=alert_type,
            tags=[
                f"node:{node_name}",
                f"check:{check_type}",
                f"severity:{severity}",
                f"app:{self.app_name}",
            ],
            aggregation_key=f"vertiguard-security-{node_name}-{check_type}",
        )

    async def submit_incident_event(
        self,
        incident_id: str,
        title: str,
        severity: str,
        details: Optional[dict[str, Any]] = None,
    ) -> Optional[dict]:
        """
        Submit an incident creation event.

        Args:
            incident_id: Datadog incident ID.
            title: Incident title.
            severity: Incident severity.
            details: Additional details.

        Returns:
            Event info dict or None on failure.
        """
        details_text = ""
        if details:
            details_text = "\n".join(f"- **{k}:** {v}" for k, v in details.items())

        text = f"""## Incident Created
- **ID:** {incident_id}
- **Title:** {title}
- **Severity:** {severity}

## Details
{details_text or "No additional details"}
"""

        return await self.client.submit_event(
            title=f"VertiGuard Incident: {title}",
            text=text,
            alert_type="error" if severity in ("SEV-1", "SEV-2") else "warning",
            priority="normal",
            tags=[
                f"incident_id:{incident_id}",
                f"severity:{severity}",
                f"app:{self.app_name}",
            ],
            aggregation_key=f"vertiguard-incident-{incident_id}",
        )
