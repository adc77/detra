"""Notification handlers for Slack, PagerDuty, and webhooks."""

import time
from typing import Any, Optional

import httpx
import structlog

from detra.config.schema import (
    IntegrationsConfig,
    PagerDutyConfig,
    SlackConfig,
    WebhookConfig,
)

logger = structlog.get_logger()


class NotificationManager:
    """
    Manages notifications to external services.

    Supports Slack, PagerDuty, and custom webhooks.
    """

    def __init__(self, config: IntegrationsConfig):
        """
        Initialize the notification manager.

        Args:
            config: Integrations configuration.
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def notify_flag(
        self,
        node_name: str,
        score: float,
        category: str,
        reason: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Send notifications for a flag event.

        Args:
            node_name: Name of the flagged node.
            score: Adherence score.
            category: Flag category.
            reason: Reason for flagging.
            details: Additional details.
        """
        if self.config.slack.enabled:
            await self._send_slack_flag(node_name, score, category, reason, details)

        if self.config.pagerduty.enabled and score < 0.5:
            await self._send_pagerduty_alert(node_name, score, category, reason)

        for webhook in self.config.webhooks:
            if "flag_raised" in webhook.events:
                await self._send_webhook(
                    webhook,
                    {
                        "event": "flag_raised",
                        "node": node_name,
                        "score": score,
                        "category": category,
                        "reason": reason,
                        "details": details,
                    },
                )

    async def notify_incident(
        self,
        incident_id: str,
        title: str,
        severity: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Send notifications for incident creation.

        Args:
            incident_id: Datadog incident ID.
            title: Incident title.
            severity: Incident severity.
            details: Additional details.
        """
        if self.config.slack.enabled and "incident_created" in self.config.slack.notify_on:
            await self._send_slack_incident(incident_id, title, severity, details)

        if self.config.pagerduty.enabled:
            await self._send_pagerduty_incident(title, severity, details)

    async def notify_security(
        self,
        node_name: str,
        check_type: str,
        severity: str,
        details: str,
    ) -> None:
        """
        Send notifications for security issues.

        Args:
            node_name: Node where issue was detected.
            check_type: Type of security check.
            severity: Issue severity.
            details: Issue details.
        """
        if self.config.slack.enabled and "security_issue" in self.config.slack.notify_on:
            await self._send_slack_security(node_name, check_type, severity, details)

        if self.config.pagerduty.enabled and severity in ("critical", "high"):
            await self._send_pagerduty_alert(
                node_name, 0.0, "security", f"{check_type}: {details}"
            )

    async def _send_slack_flag(
        self,
        node_name: str,
        score: float,
        category: str,
        reason: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send Slack notification for flag."""
        if not self.config.slack.webhook_url:
            return

        color = "#FF0000" if score < 0.5 else "#FFA500" if score < 0.85 else "#00FF00"

        mention = ""
        if score < 0.5 and self.config.slack.mention_on_critical:
            mention = " ".join(self.config.slack.mention_on_critical)

        payload = {
            "channel": self.config.slack.channel,
            "attachments": [
                {
                    "color": color,
                    "title": f"VertiGuard Flag: {node_name}",
                    "fields": [
                        {"title": "Score", "value": f"{score:.2f}", "short": True},
                        {"title": "Category", "value": category, "short": True},
                        {"title": "Reason", "value": reason, "short": False},
                    ],
                    "footer": "VertiGuard LLM Observability",
                    "ts": int(time.time()),
                }
            ],
        }

        if mention:
            payload["text"] = mention

        await self._post_to_slack(payload)

    async def _send_slack_incident(
        self,
        incident_id: str,
        title: str,
        severity: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send Slack notification for incident."""
        if not self.config.slack.webhook_url:
            return

        severity_colors = {
            "SEV-1": "#FF0000",
            "SEV-2": "#FFA500",
            "SEV-3": "#FFFF00",
            "SEV-4": "#00FF00",
        }

        payload = {
            "channel": self.config.slack.channel,
            "attachments": [
                {
                    "color": severity_colors.get(severity, "#808080"),
                    "title": f"Incident Created: {title}",
                    "fields": [
                        {"title": "Incident ID", "value": incident_id, "short": True},
                        {"title": "Severity", "value": severity, "short": True},
                    ],
                    "footer": "VertiGuard LLM Observability",
                }
            ],
        }

        await self._post_to_slack(payload)

    async def _send_slack_security(
        self,
        node_name: str,
        check_type: str,
        severity: str,
        details: str,
    ) -> None:
        """Send Slack notification for security issue."""
        if not self.config.slack.webhook_url:
            return

        color = "#FF0000" if severity in ("critical", "high") else "#FFA500"

        payload = {
            "channel": self.config.slack.channel,
            "attachments": [
                {
                    "color": color,
                    "title": f"Security Issue: {check_type}",
                    "fields": [
                        {"title": "Node", "value": node_name, "short": True},
                        {"title": "Severity", "value": severity, "short": True},
                        {"title": "Details", "value": details, "short": False},
                    ],
                    "footer": "VertiGuard Security",
                    "ts": int(time.time()),
                }
            ],
        }

        await self._post_to_slack(payload)

    async def _post_to_slack(self, payload: dict[str, Any]) -> None:
        """Post a payload to Slack."""
        try:
            client = await self._get_client()
            response = await client.post(
                self.config.slack.webhook_url,
                json=payload,
            )
            response.raise_for_status()
            logger.debug("Slack notification sent")
        except Exception as e:
            logger.error("Failed to send Slack notification", error=str(e))

    async def _send_pagerduty_alert(
        self,
        node_name: str,
        score: float,
        category: str,
        reason: str,
    ) -> None:
        """Send PagerDuty alert."""
        if not self.config.pagerduty.integration_key:
            return

        severity = "critical" if score < 0.3 else "error" if score < 0.5 else "warning"
        pd_severity = self.config.pagerduty.severity_mapping.get(severity, severity)

        payload = {
            "routing_key": self.config.pagerduty.integration_key,
            "event_action": "trigger",
            "dedup_key": f"vertiguard-{node_name}-{category}",
            "payload": {
                "summary": f"VertiGuard: {node_name} flagged - {reason}",
                "severity": pd_severity,
                "source": "vertiguard",
                "component": node_name,
                "custom_details": {
                    "score": score,
                    "category": category,
                    "reason": reason,
                },
            },
        }

        try:
            client = await self._get_client()
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            response.raise_for_status()
            logger.info("PagerDuty alert sent", node=node_name)
        except Exception as e:
            logger.error("Failed to send PagerDuty alert", error=str(e))

    async def _send_pagerduty_incident(
        self,
        title: str,
        severity: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send PagerDuty incident."""
        if not self.config.pagerduty.integration_key:
            return

        pd_severity = self.config.pagerduty.severity_mapping.get(
            severity.lower().replace("sev-", ""), "warning"
        )

        payload = {
            "routing_key": self.config.pagerduty.integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"VertiGuard Incident: {title}",
                "severity": pd_severity,
                "source": "vertiguard",
                "custom_details": details or {},
            },
        }

        try:
            client = await self._get_client()
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            response.raise_for_status()
            logger.info("PagerDuty incident sent", title=title)
        except Exception as e:
            logger.error("Failed to send PagerDuty incident", error=str(e))

    async def _send_webhook(
        self, config: WebhookConfig, data: dict[str, Any]
    ) -> None:
        """Send to custom webhook."""
        try:
            client = await self._get_client()
            response = await client.post(
                config.url,
                json=data,
                headers=config.headers,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            logger.info("Webhook sent", url=config.url)
        except Exception as e:
            logger.error("Failed to send webhook", url=config.url, error=str(e))

    async def send_slack(
        self,
        message: str,
        channel: Optional[str] = None,
        severity: str = "info",
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        """
        Send a Slack notification.

        Args:
            message: Message text.
            channel: Channel to send to (uses config default if not provided).
            severity: Severity level (info, warning, critical).
            blocks: Optional Slack block kit blocks.

        Returns:
            True if sent successfully, False if disabled or failed.
        """
        if not self.config.slack.enabled:
            return False

        if not self.config.slack.webhook_url:
            return False

        target_channel = channel or self.config.slack.channel

        severity_colors = {
            "critical": "#FF0000",
            "warning": "#FFA500",
            "error": "#FF0000",
            "info": "#00FF00",
        }

        payload: dict[str, Any] = {
            "channel": target_channel,
            "text": message,
        }

        if blocks:
            payload["blocks"] = blocks
        else:
            payload["attachments"] = [
                {
                    "color": severity_colors.get(severity.lower(), "#808080"),
                    "text": message,
                    "footer": "VertiGuard",
                    "ts": int(time.time()),
                }
            ]

        try:
            await self._post_to_slack(payload)
            return True
        except Exception:
            return False

    async def send_pagerduty(
        self,
        title: str,
        description: str,
        severity: str = "warning",
    ) -> bool:
        """
        Send a PagerDuty event.

        Args:
            title: Event title.
            description: Event description.
            severity: Severity level (critical, error, warning, info).

        Returns:
            True if sent successfully, False if disabled or failed.
        """
        if not self.config.pagerduty or not self.config.pagerduty.enabled:
            return False

        if not self.config.pagerduty.integration_key:
            return False

        pd_severity = self.config.pagerduty.severity_mapping.get(
            severity.lower(), severity.lower()
        )

        payload = {
            "routing_key": self.config.pagerduty.integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": title,
                "severity": pd_severity,
                "source": "vertiguard",
                "custom_details": {
                    "description": description,
                },
            },
        }

        try:
            client = await self._get_client()
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            response.raise_for_status()
            logger.info("PagerDuty event sent", title=title)
            return True
        except Exception as e:
            logger.error("Failed to send PagerDuty event", error=str(e))
            return False

    async def send_webhook(
        self,
        event_type: str,
        payload: dict[str, Any],
        webhook_name: Optional[str] = None,
    ) -> bool:
        """
        Send a webhook notification.

        Args:
            event_type: Type of event.
            payload: Payload data to send.
            webhook_name: Optional specific webhook name to use.

        Returns:
            True if sent successfully, False if no webhooks or failed.
        """
        if not self.config.webhooks:
            return False

        webhooks_to_use = (
            [w for w in self.config.webhooks if w.name == webhook_name]
            if webhook_name
            else self.config.webhooks
        )

        if not webhooks_to_use:
            return False

        success = False
        for webhook in webhooks_to_use:
            if event_type in webhook.events:
                data = {
                    "event": event_type,
                    **payload,
                }
                try:
                    await self._send_webhook(webhook, data)
                    success = True
                except Exception:
                    pass  # Continue to next webhook

        return success
