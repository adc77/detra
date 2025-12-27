"""Tests for the telemetry module."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from vertiguard.config.schema import DatadogConfig, VertiGuardConfig
from vertiguard.telemetry.datadog_client import DatadogClient
from vertiguard.telemetry.llmobs_bridge import LLMObsBridge


class TestDatadogClient:
    """Tests for DatadogClient."""

    @pytest.fixture
    def config(self, sample_datadog_config):
        """Get Datadog config for testing."""
        return sample_datadog_config

    @pytest.fixture
    def client(self, config):
        """Create a DatadogClient with mocked APIs."""
        with patch("vertiguard.telemetry.datadog_client.MetricsApi") as mock_metrics:
            with patch("vertiguard.telemetry.datadog_client.EventsApi") as mock_events:
                with patch("vertiguard.telemetry.datadog_client.MonitorsApi") as mock_monitors:
                    with patch("vertiguard.telemetry.datadog_client.DashboardsApi") as mock_dashboards:
                        with patch("vertiguard.telemetry.datadog_client.IncidentsApi") as mock_incidents:
                            with patch("vertiguard.telemetry.datadog_client.ServiceChecksApi") as mock_service_checks:
                                client = DatadogClient(config)

                                # Setup mock return values
                                client._metrics_api.submit_metrics = MagicMock(
                                    return_value={"status": "ok"}
                                )
                                client._events_api.create_event = MagicMock(
                                    return_value={"event": {"id": 123}}
                                )
                                client._monitors_api.create_monitor = MagicMock(
                                    return_value=MagicMock(id=456, name="test")
                                )
                                client._dashboards_api.create_dashboard = MagicMock(
                                    return_value=MagicMock(id="abc", title="Test", url="http://test")
                                )
                                client._service_checks_api.submit_service_check = MagicMock(
                                    return_value={"status": "ok"}
                                )

                                return client

    @pytest.mark.asyncio
    async def test_submit_metrics(self, client):
        """Test submitting metrics to Datadog."""
        metrics = [
            {
                "metric": "vertiguard.test.metric",
                "type": "gauge",
                "points": [[1234567890, 1.5]],
                "tags": ["node:test"],
            }
        ]

        result = await client.submit_metrics(metrics)
        assert result is True

    @pytest.mark.asyncio
    async def test_submit_event(self, client):
        """Test submitting an event to Datadog."""
        result = await client.submit_event(
            title="Test Event",
            text="This is a test event",
            alert_type="info",
            tags=["test:true"],
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_submit_event_with_aggregation(self, client):
        """Test submitting event with aggregation key."""
        result = await client.submit_event(
            title="Aggregated Event",
            text="Test",
            alert_type="warning",
            tags=[],
            aggregation_key="test-agg-key",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_create_monitor(self, client):
        """Test creating a Datadog monitor."""
        result = await client.create_monitor(
            name="Test Monitor",
            query="avg(last_5m):avg:vertiguard.test{*} > 0.5",
            message="Test alert",
            monitor_type="metric alert",
            tags=["test:true"],
        )
        assert result is not None
        assert "id" in result or hasattr(result, "id")

    @pytest.mark.asyncio
    async def test_create_dashboard(self, client):
        """Test creating a Datadog dashboard."""
        dashboard_def = {
            "title": "Test Dashboard",
            "layout_type": "ordered",
            "widgets": [],
        }

        result = await client.create_dashboard(dashboard_def)
        assert result is not None

    @pytest.mark.asyncio
    async def test_submit_service_check(self, client):
        """Test submitting a service check."""
        result = await client.submit_service_check(
            check="vertiguard.test.health",
            status=0,  # OK
            message="Service is healthy",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_submit_service_check_warning(self, client):
        """Test submitting a warning service check."""
        result = await client.submit_service_check(
            check="vertiguard.test.health",
            status=1,  # Warning
            message="Service is degraded",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        await client.close()
        # Should not raise

    @pytest.mark.asyncio
    async def test_submit_empty_metrics(self, client):
        """Test submitting empty metrics list."""
        result = await client.submit_metrics([])
        # Should handle gracefully


class TestLLMObsBridge:
    """Tests for LLMObsBridge."""

    @pytest.fixture
    def config(self, sample_vertiguard_config):
        """Get VertiGuard config for testing."""
        return sample_vertiguard_config

    @pytest.fixture
    def bridge(self, config):
        """Create an LLMObsBridge with mocked LLMObs."""
        with patch("vertiguard.telemetry.llmobs_bridge.LLMObs") as mock_llmobs:
            mock_llmobs.enable = MagicMock()
            mock_llmobs.disable = MagicMock()
            mock_llmobs.flush = MagicMock()
            mock_llmobs.annotate = MagicMock()
            mock_llmobs.submit_evaluation = MagicMock()
            mock_llmobs.workflow = MagicMock()
            mock_llmobs.llm = MagicMock()
            mock_llmobs.task = MagicMock()
            mock_llmobs.agent = MagicMock()

            bridge = LLMObsBridge(config)
            bridge._llmobs = mock_llmobs
            return bridge

    def test_enable(self, bridge):
        """Test enabling LLM Observability."""
        bridge.enable()
        bridge._llmobs.enable.assert_called()

    def test_disable(self, bridge):
        """Test disabling LLM Observability."""
        bridge.disable()
        bridge._llmobs.disable.assert_called()

    def test_flush(self, bridge):
        """Test flushing telemetry."""
        bridge.flush()
        bridge._llmobs.flush.assert_called()

    def test_workflow_context(self, bridge):
        """Test creating workflow context."""
        bridge._llmobs.workflow.return_value = MagicMock()
        ctx = bridge.workflow("test_workflow")
        assert ctx is not None

    def test_llm_context(self, bridge):
        """Test creating LLM span context."""
        bridge._llmobs.llm.return_value = MagicMock()
        ctx = bridge.llm("test_llm", model_name="test-model")
        assert ctx is not None

    def test_task_context(self, bridge):
        """Test creating task context."""
        bridge._llmobs.task.return_value = MagicMock()
        ctx = bridge.task("test_task")
        assert ctx is not None

    def test_agent_context(self, bridge):
        """Test creating agent context."""
        bridge._llmobs.agent.return_value = MagicMock()
        ctx = bridge.agent("test_agent")
        assert ctx is not None

    def test_annotate(self, bridge):
        """Test annotating a span."""
        mock_span = MagicMock()
        bridge.annotate(mock_span, input_data="test input", output_data="test output")
        bridge._llmobs.annotate.assert_called()

    def test_submit_evaluation(self, bridge):
        """Test submitting an evaluation."""
        mock_span = MagicMock()
        bridge.submit_evaluation(
            span=mock_span,
            label="adherence_score",
            metric_type="score",
            value=0.95,
        )
        bridge._llmobs.submit_evaluation.assert_called()


class TestDatadogClientErrorHandling:
    """Tests for DatadogClient error handling."""

    @pytest.fixture
    def failing_client(self, sample_datadog_config):
        """Create a client that simulates API failures."""
        with patch("vertiguard.telemetry.datadog_client.MetricsApi") as mock_metrics:
            with patch("vertiguard.telemetry.datadog_client.EventsApi") as mock_events:
                with patch("vertiguard.telemetry.datadog_client.MonitorsApi"):
                    with patch("vertiguard.telemetry.datadog_client.DashboardsApi"):
                        with patch("vertiguard.telemetry.datadog_client.IncidentsApi"):
                            with patch("vertiguard.telemetry.datadog_client.ServiceChecksApi"):
                                client = DatadogClient(sample_datadog_config)

                                # Setup to raise errors
                                client._metrics_api.submit_metrics = MagicMock(
                                    side_effect=Exception("API Error")
                                )
                                client._events_api.create_event = MagicMock(
                                    side_effect=Exception("API Error")
                                )

                                return client

    @pytest.mark.asyncio
    async def test_submit_metrics_handles_error(self, failing_client):
        """Test that metrics submission handles API errors."""
        result = await failing_client.submit_metrics([
            {"metric": "test", "type": "gauge", "points": [[0, 1]], "tags": []}
        ])
        # Should return False or handle error gracefully
        assert result is False or result is None

    @pytest.mark.asyncio
    async def test_submit_event_handles_error(self, failing_client):
        """Test that event submission handles API errors."""
        result = await failing_client.submit_event(
            title="Test",
            text="Test",
            alert_type="info",
            tags=[],
        )
        assert result is False or result is None


class TestEdgeCases:
    """Edge case tests for telemetry module."""

    @pytest.mark.asyncio
    async def test_client_with_empty_tags(self, sample_datadog_config):
        """Test submitting data with empty tags."""
        with patch("vertiguard.telemetry.datadog_client.MetricsApi") as mock_api:
            with patch("vertiguard.telemetry.datadog_client.EventsApi"):
                with patch("vertiguard.telemetry.datadog_client.MonitorsApi"):
                    with patch("vertiguard.telemetry.datadog_client.DashboardsApi"):
                        with patch("vertiguard.telemetry.datadog_client.IncidentsApi"):
                            with patch("vertiguard.telemetry.datadog_client.ServiceChecksApi"):
                                client = DatadogClient(sample_datadog_config)
                                client._metrics_api.submit_metrics = MagicMock(
                                    return_value={"status": "ok"}
                                )

                                result = await client.submit_metrics([
                                    {"metric": "test", "type": "count", "points": [[0, 1]], "tags": []}
                                ])
                                assert result is True

    @pytest.mark.asyncio
    async def test_client_with_special_characters_in_tags(self, sample_datadog_config):
        """Test tags with special characters."""
        with patch("vertiguard.telemetry.datadog_client.MetricsApi") as mock_api:
            with patch("vertiguard.telemetry.datadog_client.EventsApi"):
                with patch("vertiguard.telemetry.datadog_client.MonitorsApi"):
                    with patch("vertiguard.telemetry.datadog_client.DashboardsApi"):
                        with patch("vertiguard.telemetry.datadog_client.IncidentsApi"):
                            with patch("vertiguard.telemetry.datadog_client.ServiceChecksApi"):
                                client = DatadogClient(sample_datadog_config)
                                client._metrics_api.submit_metrics = MagicMock(
                                    return_value={"status": "ok"}
                                )

                                result = await client.submit_metrics([
                                    {
                                        "metric": "test",
                                        "type": "gauge",
                                        "points": [[0, 1]],
                                        "tags": ["node:test/with/slashes", "env:prod-v2.1"]
                                    }
                                ])
                                # Should handle or sanitize tags

    @pytest.mark.asyncio
    async def test_large_metrics_batch(self, sample_datadog_config):
        """Test submitting a large batch of metrics."""
        with patch("vertiguard.telemetry.datadog_client.MetricsApi"):
            with patch("vertiguard.telemetry.datadog_client.EventsApi"):
                with patch("vertiguard.telemetry.datadog_client.MonitorsApi"):
                    with patch("vertiguard.telemetry.datadog_client.DashboardsApi"):
                        with patch("vertiguard.telemetry.datadog_client.IncidentsApi"):
                            with patch("vertiguard.telemetry.datadog_client.ServiceChecksApi"):
                                client = DatadogClient(sample_datadog_config)
                                client._metrics_api.submit_metrics = MagicMock(
                                    return_value={"status": "ok"}
                                )

                                # Create 1000 metrics
                                metrics = [
                                    {
                                        "metric": f"test.metric.{i}",
                                        "type": "gauge",
                                        "points": [[i, i * 0.1]],
                                        "tags": [f"index:{i}"]
                                    }
                                    for i in range(1000)
                                ]

                                result = await client.submit_metrics(metrics)
                                # Should handle large batches

    def test_bridge_multiple_enable_disable_cycles(self, sample_vertiguard_config):
        """Test enabling and disabling multiple times."""
        with patch("vertiguard.telemetry.llmobs_bridge.LLMObs") as mock_llmobs:
            bridge = LLMObsBridge(sample_vertiguard_config)
            bridge._llmobs = mock_llmobs

            # Multiple enable/disable cycles
            for _ in range(5):
                bridge.enable()
                bridge.disable()

            # Should not raise
