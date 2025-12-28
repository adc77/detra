"""Unified Datadog API client for all telemetry operations."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import structlog
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.api.service_checks_api import ServiceChecksApi
from datadog_api_client.v1.model.event_create_request import EventCreateRequest
from datadog_api_client.v1.model.monitor import Monitor
from datadog_api_client.v1.model.monitor_type import MonitorType
from datadog_api_client.v1.model.service_check import ServiceCheck
from datadog_api_client.v1.model.service_check_status import ServiceCheckStatus
from datadog_api_client.v2.api.incidents_api import IncidentsApi
from datadog_api_client.v2.api.metrics_api import MetricsApi
from datadog_api_client.v2.model.incident_create_attributes import IncidentCreateAttributes
from datadog_api_client.v2.model.incident_create_data import IncidentCreateData
from datadog_api_client.v2.model.incident_create_request import IncidentCreateRequest
from datadog_api_client.v2.model.incident_type import IncidentType
from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
from datadog_api_client.v2.model.metric_payload import MetricPayload
from datadog_api_client.v2.model.metric_point import MetricPoint
from datadog_api_client.v2.model.metric_series import MetricSeries

from detra.config.schema import DatadogConfig

logger = structlog.get_logger()


class DatadogClient:
    """
    Centralized async Datadog API client for all telemetry operations.

    Provides methods for submitting metrics, events, creating monitors,
    dashboards, and incidents.
    """

    def __init__(self, config: DatadogConfig):
        """
        Initialize the Datadog client.

        Args:
            config: Datadog configuration.
        """
        self.config = config
        self.configuration = Configuration()
        self.configuration.api_key["apiKeyAuth"] = config.api_key
        self.configuration.api_key["appKeyAuth"] = config.app_key
        self.configuration.server_variables["site"] = config.site

        # Enable retry for resilience
        self.configuration.enable_retry = True
        self.configuration.max_retries = 3

        self._base_tags = self._build_base_tags()
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _build_base_tags(self) -> list[str]:
        """Build base tags for all submissions."""
        tags = []
        if self.config.service:
            tags.append(f"service:{self.config.service}")
        if self.config.env:
            tags.append(f"env:{self.config.env}")
        if self.config.version:
            tags.append(f"version:{self.config.version}")
        return tags

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: func(*args, **kwargs)
        )

    # =========================================================================
    # METRICS
    # =========================================================================

    async def submit_metrics(self, metrics: list[dict[str, Any]]) -> bool:
        """
        Submit custom metrics to Datadog.

        Args:
            metrics: List of metric dictionaries with keys:
                - metric: Metric name
                - type: gauge, count, or distribution
                - points: List of [timestamp, value] pairs
                - tags: Optional list of tags

        Returns:
            True if successful, False otherwise.
        """
        try:
            return await self._run_sync(self._submit_metrics_sync, metrics)
        except Exception as e:
            logger.error("Failed to submit metrics", error=str(e))
            return False

    def _submit_metrics_sync(self, metrics: list[dict[str, Any]]) -> bool:
        """Synchronous implementation of metric submission."""
        import time

        with ApiClient(self.configuration) as api_client:
            api = MetricsApi(api_client)

            series = []
            for m in metrics:
                tags = self._base_tags + m.get("tags", [])

                points = []
                for p in m["points"]:
                    timestamp = int(p[0]) if p[0] else int(time.time())
                    points.append(MetricPoint(timestamp=timestamp, value=float(p[1])))

                metric_type = m.get("type", "gauge")
                intake_type = {
                    "gauge": MetricIntakeType.GAUGE,
                    "count": MetricIntakeType.COUNT,
                    "rate": MetricIntakeType.RATE,
                }.get(metric_type, MetricIntakeType.GAUGE)

                series.append(
                    MetricSeries(
                        metric=m["metric"],
                        type=intake_type,
                        points=points,
                        tags=tags,
                    )
                )

            payload = MetricPayload(series=series)
            api.submit_metrics(body=payload)

            logger.debug("Metrics submitted", count=len(metrics))
            return True

    async def submit_gauge(
        self, metric: str, value: float, tags: Optional[list[str]] = None
    ) -> bool:
        """Submit a single gauge metric."""
        import time

        return await self.submit_metrics(
            [
                {
                    "metric": metric,
                    "type": "gauge",
                    "points": [[time.time(), value]],
                    "tags": tags or [],
                }
            ]
        )

    async def submit_count(
        self, metric: str, value: int, tags: Optional[list[str]] = None
    ) -> bool:
        """Submit a count metric."""
        import time

        return await self.submit_metrics(
            [
                {
                    "metric": metric,
                    "type": "count",
                    "points": [[time.time(), value]],
                    "tags": tags or [],
                }
            ]
        )

    # =========================================================================
    # EVENTS
    # =========================================================================

    async def submit_event(
        self,
        title: str,
        text: str,
        alert_type: str = "info",
        priority: str = "normal",
        tags: Optional[list[str]] = None,
        aggregation_key: Optional[str] = None,
        source_type_name: str = "vertiguard",
    ) -> Optional[dict]:
        """
        Submit an event to Datadog.

        Args:
            title: Event title.
            text: Event text/body.
            alert_type: One of: error, warning, info, success.
            priority: One of: normal, low.
            tags: Additional tags.
            aggregation_key: Key to aggregate related events.
            source_type_name: Source type for the event.

        Returns:
            Event info dict with id and url, or None on failure.
        """
        try:
            return await self._run_sync(
                self._submit_event_sync,
                title,
                text,
                alert_type,
                priority,
                tags,
                aggregation_key,
                source_type_name,
            )
        except Exception as e:
            logger.error("Failed to submit event", error=str(e))
            return None

    def _submit_event_sync(
        self,
        title: str,
        text: str,
        alert_type: str,
        priority: str,
        tags: Optional[list[str]],
        aggregation_key: Optional[str],
        source_type_name: str,
    ) -> Optional[dict]:
        """Synchronous implementation of event submission."""
        with ApiClient(self.configuration) as api_client:
            api = EventsApi(api_client)

            body = EventCreateRequest(
                title=title,
                text=text,
                alert_type=alert_type,
                priority=priority,
                tags=self._base_tags + (tags or []),
                aggregation_key=aggregation_key,
                source_type_name=source_type_name,
            )

            response = api.create_event(body=body)
            logger.info("Event submitted", title=title, event_id=response.event.id)
            return {"id": response.event.id, "url": response.event.url}

    # =========================================================================
    # MONITORS
    # =========================================================================

    async def create_monitor(
        self,
        name: str,
        query: str,
        message: str,
        monitor_type: str = "metric alert",
        thresholds: Optional[dict[str, float]] = None,
        tags: Optional[list[str]] = None,
        priority: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Create a Datadog monitor.

        Args:
            name: Monitor name.
            query: Monitor query.
            message: Alert message.
            monitor_type: Type of monitor.
            thresholds: Threshold values.
            tags: Monitor tags.
            priority: Monitor priority (1-5).

        Returns:
            Monitor info dict with id and name, or None on failure.
        """
        try:
            return await self._run_sync(
                self._create_monitor_sync,
                name,
                query,
                message,
                monitor_type,
                thresholds,
                tags,
                priority,
            )
        except Exception as e:
            logger.error("Failed to create monitor", error=str(e), name=name)
            return None

    def _create_monitor_sync(
        self,
        name: str,
        query: str,
        message: str,
        monitor_type: str,
        thresholds: Optional[dict[str, float]],
        tags: Optional[list[str]],
        priority: Optional[int],
    ) -> Optional[dict]:
        """Synchronous implementation of monitor creation."""
        with ApiClient(self.configuration) as api_client:
            api = MonitorsApi(api_client)

            options = {"thresholds": thresholds or {"critical": 1}}
            if priority:
                options["priority"] = priority

            body = Monitor(
                name=name,
                type=MonitorType(monitor_type),
                query=query,
                message=message,
                tags=self._base_tags + (tags or []),
                options=options,
            )

            response = api.create_monitor(body=body)
            logger.info("Monitor created", name=name, id=response.id)
            return {"id": response.id, "name": response.name}

    async def list_monitors(self, name_filter: Optional[str] = None) -> list[dict]:
        """List existing monitors."""
        try:
            return await self._run_sync(self._list_monitors_sync, name_filter)
        except Exception as e:
            logger.error("Failed to list monitors", error=str(e))
            return []

    def _list_monitors_sync(self, name_filter: Optional[str]) -> list[dict]:
        """Synchronous implementation of monitor listing."""
        with ApiClient(self.configuration) as api_client:
            api = MonitorsApi(api_client)

            kwargs = {}
            if name_filter:
                kwargs["name"] = name_filter

            response = api.list_monitors(**kwargs)
            return [{"id": m.id, "name": m.name, "query": m.query} for m in response]

    # =========================================================================
    # DASHBOARDS
    # =========================================================================

    async def create_dashboard(self, dashboard_definition: dict) -> Optional[dict]:
        """
        Create a Datadog dashboard.

        Args:
            dashboard_definition: Dashboard JSON definition.

        Returns:
            Dashboard info dict with id, title, and url, or None on failure.
        """
        try:
            return await self._run_sync(
                self._create_dashboard_sync, dashboard_definition
            )
        except Exception as e:
            logger.error("Failed to create dashboard", error=str(e))
            return None

    def _create_dashboard_sync(self, dashboard_definition: dict) -> Optional[dict]:
        """Synchronous implementation of dashboard creation."""
        with ApiClient(self.configuration) as api_client:
            api = DashboardsApi(api_client)

            response = api.create_dashboard(body=dashboard_definition)
            logger.info("Dashboard created", title=response.title, id=response.id)
            return {
                "id": response.id,
                "title": response.title,
                "url": response.url,
            }

    # =========================================================================
    # INCIDENTS
    # =========================================================================

    async def create_incident(
        self,
        title: str,
        severity: str = "SEV-3",
        customer_impacted: bool = False,
    ) -> Optional[dict]:
        """
        Create an incident.

        Args:
            title: Incident title.
            severity: Severity level (SEV-1 through SEV-5).
            customer_impacted: Whether customers are impacted.

        Returns:
            Incident info dict with id, or None on failure.
        """
        try:
            return await self._run_sync(
                self._create_incident_sync, title, severity, customer_impacted
            )
        except Exception as e:
            logger.error("Failed to create incident", error=str(e))
            return None

    def _create_incident_sync(
        self, title: str, severity: str, customer_impacted: bool
    ) -> Optional[dict]:
        """Synchronous implementation of incident creation."""
        with ApiClient(self.configuration) as api_client:
            api = IncidentsApi(api_client)

            body = IncidentCreateRequest(
                data=IncidentCreateData(
                    type=IncidentType("incidents"),
                    attributes=IncidentCreateAttributes(
                        title=title,
                        customer_impacted=customer_impacted,
                        fields={"severity": {"type": "dropdown", "value": severity}},
                    ),
                )
            )

            response = api.create_incident(body=body)
            return {"id": response.data.id}

    # =========================================================================
    # SERVICE CHECKS
    # =========================================================================

    async def submit_service_check(
        self,
        check: str,
        status: int,
        message: str = "",
        tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit a service check.

        Args:
            check: Check name.
            status: 0=OK, 1=Warning, 2=Critical, 3=Unknown.
            message: Check message.
            tags: Additional tags.

        Returns:
            True if successful, False otherwise.
        """
        try:
            return await self._run_sync(
                self._submit_service_check_sync, check, status, message, tags
            )
        except Exception as e:
            logger.error("Failed to submit service check", error=str(e))
            return False

    def _submit_service_check_sync(
        self,
        check: str,
        status: int,
        message: str,
        tags: Optional[list[str]],
    ) -> bool:
        """Synchronous implementation of service check submission."""
        with ApiClient(self.configuration) as api_client:
            api = ServiceChecksApi(api_client)

            body = [
                ServiceCheck(
                    check=check,
                    host_name="vertiguard",
                    status=ServiceCheckStatus(status),
                    message=message,
                    tags=self._base_tags + (tags or []),
                )
            ]

            api.submit_service_check(body=body)
            return True

    async def close(self) -> None:
        """Close the client and release resources."""
        self._executor.shutdown(wait=False)
