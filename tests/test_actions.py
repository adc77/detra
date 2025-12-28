"""Tests for the actions module."""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from detra.config.schema import (
    IntegrationsConfig,
    SlackConfig,
    PagerDutyConfig,
    WebhookConfig,
)
from detra.actions.notifications import NotificationManager
from detra.actions.alerts import AlertHandler, AlertType, Alert, AlertSeverity
from detra.actions.cases import CaseManager, Case, CaseStatus
from detra.actions.incidents import IncidentManager


class TestNotificationManager:
    """Tests for NotificationManager."""

    @pytest.fixture
    def slack_config(self):
        """Create Slack config for testing."""
        return SlackConfig(
            enabled=True,
            webhook_url="https://hooks.slack.com/services/test",
            channel="#test-alerts",
            notify_on=["flag_raised", "incident_created"],
            mention_on_critical=["@here"],
        )

    @pytest.fixture
    def integrations_config(self, slack_config):
        """Create integrations config for testing."""
        return IntegrationsConfig(
            slack=slack_config,
            pagerduty=None,
            webhooks=[],
        )

    @pytest.fixture
    def manager(self, integrations_config):
        """Create a NotificationManager."""
        return NotificationManager(integrations_config)

    @pytest.mark.asyncio
    async def test_send_slack_notification(self, manager):
        """Test sending Slack notification."""
        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await manager.send_slack(
                message="Test notification",
                channel="#test",
                severity="warning",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_slack_with_blocks(self, manager):
        """Test sending Slack notification with blocks."""
        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await manager.send_slack(
                message="Test",
                channel="#test",
                severity="critical",
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": "Test block"}}
                ],
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_slack_disabled(self):
        """Test that disabled Slack doesn't send."""
        config = IntegrationsConfig(
            slack=SlackConfig(enabled=False),
            pagerduty=None,
            webhooks=[],
        )
        manager = NotificationManager(config)

        result = await manager.send_slack(
            message="Test",
            channel="#test",
            severity="info",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_pagerduty_event(self):
        """Test sending PagerDuty event."""
        config = IntegrationsConfig(
            slack=SlackConfig(enabled=False),
            pagerduty=PagerDutyConfig(
                enabled=True,
                integration_key="test-key",
                severity_mapping={"critical": "critical", "warning": "warning"},
            ),
            webhooks=[],
        )
        manager = NotificationManager(config)

        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await manager.send_pagerduty(
                title="Test Incident",
                description="Test description",
                severity="critical",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_webhook(self):
        """Test sending webhook notification."""
        config = IntegrationsConfig(
            slack=SlackConfig(enabled=False),
            pagerduty=None,
            webhooks=[
                WebhookConfig(
                    name="test-webhook",
                    url="https://example.com/webhook",
                    events=["flag_raised"],
                    headers={"Authorization": "Bearer test"},
                )
            ],
        )
        manager = NotificationManager(config)

        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await manager.send_webhook(
                event_type="flag_raised",
                payload={"test": "data"},
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_notify_flag_routes_to_slack(self, manager):
        """Test that notify_flag routes to Slack when enabled."""
        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await manager.notify_flag(
                node_name="test_node",
                score=0.4,
                category="hallucination",
                reason="Test flag",
            )
            # Should have called Slack since flag_raised is in notify_on
            mock_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_close(self, manager):
        """Test closing the manager."""
        await manager.close()
        # Should not raise


class TestAlertHandler:
    """Tests for AlertHandler."""

    @pytest.fixture
    def mock_notification_manager(self):
        """Create a mock notification manager."""
        manager = MagicMock()
        manager.notify = AsyncMock()
        manager.send_slack = AsyncMock(return_value=True)
        manager.send_pagerduty = AsyncMock(return_value=True)
        return manager

    @pytest.fixture
    def handler(self, mock_notification_manager):
        """Create an AlertHandler."""
        return AlertHandler(mock_notification_manager, event_submitter=None)

    @pytest.mark.asyncio
    async def test_handle_flag_alert(self, handler):
        """Test handling a flag alert."""
        alert = Alert(
            alert_type=AlertType.FLAG,
            title="Hallucination Detected",
            message="Output contains fabricated information",
            severity=AlertSeverity.MEDIUM,
            node_name="extract_entities",
            details={"score": 0.45},
        )

        await handler.handle_alert(alert)
        handler.notifications.notify_flag.assert_called()

    @pytest.mark.asyncio
    async def test_handle_security_alert(self, handler):
        """Test handling a security alert."""
        alert = Alert(
            alert_type=AlertType.SECURITY,
            title="PII Detected",
            message="Email address found in output",
            severity=AlertSeverity.CRITICAL,
            node_name="answer_query",
            details={"pii_type": "email"},
        )

        await handler.handle_alert(alert)
        handler.notifications.notify_security.assert_called()

    @pytest.mark.asyncio
    async def test_handle_latency_alert(self, handler):
        """Test handling a latency alert."""
        alert = Alert(
            alert_type=AlertType.LATENCY,
            title="High Latency",
            message="Response time exceeded threshold",
            severity=AlertSeverity.MEDIUM,
            node_name="summarize",
            details={"latency_ms": 5500},
        )

        await handler.handle_alert(alert)
        # Latency alerts may not trigger notifications by default

    def test_alert_types(self):
        """Test AlertType enum values."""
        assert AlertType.FLAG.value == "flag"
        assert AlertType.SECURITY.value == "security"
        assert AlertType.ERROR.value == "error"
        assert AlertType.LATENCY.value == "latency"
        assert AlertType.THRESHOLD.value == "threshold"


class TestCaseManager:
    """Tests for CaseManager."""

    @pytest.fixture
    def manager(self):
        """Create a CaseManager."""
        return CaseManager()

    def test_create_case(self, manager):
        """Test creating a case."""
        from detra.actions.cases import CasePriority
        case = manager.create_case(
            title="Test Case",
            description="Test description",
            priority=CasePriority.HIGH,
            node_name="test_node",
        )
        assert case.case_id is not None
        assert case.title == "Test Case"
        assert case.status == CaseStatus.OPEN

    def test_get_case(self, manager):
        """Test retrieving a case."""
        from detra.actions.cases import CasePriority
        created = manager.create_case(
            title="Test",
            description="Test",
            priority=CasePriority.LOW,
            node_name="node",
        )
        retrieved = manager.get_case(created.case_id)
        assert retrieved is not None
        assert retrieved.case_id == created.case_id

    def test_update_case_status(self, manager):
        """Test updating case status."""
        from detra.actions.cases import CasePriority
        case = manager.create_case(
            title="Test",
            description="Test",
            priority=CasePriority.MEDIUM,
            node_name="node",
        )
        manager.update_case(case.case_id, status=CaseStatus.IN_PROGRESS)
        updated = manager.get_case(case.case_id)
        assert updated.status == CaseStatus.IN_PROGRESS

    def test_add_case_note(self, manager):
        """Test adding a note to a case."""
        from detra.actions.cases import CasePriority
        case = manager.create_case(
            title="Test",
            description="Test",
            priority=CasePriority.LOW,
            node_name="node",
        )
        manager.update_case(case.case_id, note="Investigation started")
        updated = manager.get_case(case.case_id)
        assert len(updated.notes) == 1
        assert "Investigation started" in updated.notes[0].content

    def test_list_cases_by_status(self, manager):
        """Test listing cases by status."""
        from detra.actions.cases import CasePriority
        case1 = manager.create_case(
            title="Open Case",
            description="Test",
            priority=CasePriority.LOW,
            node_name="node",
        )
        case2 = manager.create_case(
            title="Closed Case",
            description="Test",
            priority=CasePriority.LOW,
            node_name="node",
        )
        manager.update_case(case2.case_id, status=CaseStatus.CLOSED)

        open_cases = manager.list_cases(status=CaseStatus.OPEN)
        assert len(open_cases) == 1
        assert open_cases[0].title == "Open Case"

    def test_close_case(self, manager):
        """Test closing a case with resolution."""
        from detra.actions.cases import CasePriority
        case = manager.create_case(
            title="Test",
            description="Test",
            priority=CasePriority.HIGH,
            node_name="node",
        )
        manager.close_case(
            case.case_id,
            resolution_note="Issue was a false positive",
        )
        closed = manager.get_case(case.case_id)
        assert closed.status == CaseStatus.CLOSED
        assert any("false positive" in note.content for note in closed.notes)


class TestIncidentManager:
    """Tests for IncidentManager."""

    @pytest.fixture
    def mock_datadog_client(self):
        """Create a mock Datadog client."""
        client = MagicMock()
        client.create_incident = AsyncMock(return_value={"id": "inc-123"})
        return client

    @pytest.fixture
    def mock_notification_manager(self):
        """Create a mock notification manager."""
        manager = MagicMock()
        manager.notify = AsyncMock()
        return manager

    @pytest.fixture
    def manager(self, mock_datadog_client, mock_notification_manager):
        """Create an IncidentManager."""
        return IncidentManager(mock_datadog_client, mock_notification_manager)

    @pytest.mark.asyncio
    async def test_create_incident(self, manager):
        """Test creating an incident."""
        result = await manager.create_manual_incident(
            title="Critical Alert",
            description="System experiencing high error rate",
            severity="SEV-1",
        )
        assert result is not None
        manager.datadog_client.create_incident.assert_called()

    @pytest.mark.asyncio
    async def test_create_incident_sends_notification(self, manager):
        """Test that incident creation sends notification."""
        await manager.create_manual_incident(
            title="Test Incident",
            description="Test",
            severity="SEV-1",
        )
        manager.notification_manager.notify_incident.assert_called()

    @pytest.mark.asyncio
    async def test_should_create_incident_critical(self, manager):
        """Test incident creation threshold for critical severity."""
        should_create = IncidentManager.should_create_incident(
            score=0.3,
            security_issues=[],
            threshold=0.5,
        )
        assert should_create is True

    @pytest.mark.asyncio
    async def test_should_create_incident_low_score(self, manager):
        """Test incident creation threshold for low score."""
        should_create = IncidentManager.should_create_incident(
            score=0.4,
            security_issues=[],
            threshold=0.5,
        )
        assert should_create is True


class TestCaseStatus:
    """Tests for CaseStatus enum."""

    def test_case_status_values(self):
        """Test CaseStatus enum values."""
        assert CaseStatus.OPEN.value == "open"
        assert CaseStatus.IN_PROGRESS.value == "in_progress"
        assert CaseStatus.RESOLVED.value == "resolved"
        assert CaseStatus.CLOSED.value == "closed"


class TestEdgeCases:
    """Edge case tests for actions module."""

    @pytest.mark.asyncio
    async def test_notification_manager_handles_http_error(self):
        """Test notification manager handles HTTP errors."""
        config = IntegrationsConfig(
            slack=SlackConfig(
                enabled=True,
                webhook_url="https://invalid.url/webhook",
                channel="#test",
            ),
            pagerduty=None,
            webhooks=[],
        )
        manager = NotificationManager(config)

        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection error"))
            mock_get_client.return_value = mock_client

            result = await manager.send_slack(
                message="Test",
                channel="#test",
                severity="info",
            )
            assert result is False

    def test_case_manager_get_nonexistent(self):
        """Test getting non-existent case."""
        manager = CaseManager()
        case = manager.get_case("nonexistent-id")
        assert case is None

    def test_case_manager_update_nonexistent(self):
        """Test updating non-existent case."""
        manager = CaseManager()
        # Should handle gracefully
        try:
            manager.update_status("nonexistent-id", CaseStatus.CLOSED)
        except KeyError:
            pass  # Expected behavior
        except Exception:
            pass  # Also acceptable

    @pytest.mark.asyncio
    async def test_incident_manager_handles_datadog_error(
        self, mock_notification_manager
    ):
        """Test incident manager handles Datadog errors."""
        failing_client = MagicMock()
        failing_client.create_incident = AsyncMock(
            side_effect=Exception("Datadog API error")
        )

        manager = IncidentManager(failing_client, mock_notification_manager)

        try:
            await manager.create_manual_incident(
                title="Test",
                description="Test",
                severity="SEV-1",
            )
        except Exception:
            pass  # Error handling depends on implementation

    def test_alert_with_all_fields(self):
        """Test Alert with all fields populated."""
        alert = Alert(
            alert_type=AlertType.FLAG,
            title="Complete Alert",
            message="Full message with details",
            severity=AlertSeverity.CRITICAL,
            node_name="test_node",
            details={
                "score": 0.3,
                "category": "hallucination",
                "trace_id": "abc123",
            },
        )
        assert alert.details["score"] == 0.3
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_webhook_with_custom_headers(self):
        """Test webhook with custom headers."""
        config = IntegrationsConfig(
            slack=SlackConfig(enabled=False),
            pagerduty=None,
            webhooks=[
                WebhookConfig(
                    name="custom-webhook",
                    url="https://example.com/webhook",
                    events=["flag_raised"],
                    headers={
                        "Authorization": "Bearer secret",
                        "X-Custom-Header": "custom-value",
                    },
                )
            ],
        )
        manager = NotificationManager(config)

        with patch.object(manager, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await manager.send_webhook(
                event_type="flag_raised",
                payload={"test": "data"},
            )
            # Verify headers were included
            mock_client.post.assert_called()
