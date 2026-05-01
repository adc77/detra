"""Datadog backend -- wraps the existing DatadogClient behind the backend protocol.

Requires: pip install detra[datadog]
"""

from __future__ import annotations

import time

try:
    from detra.telemetry.datadog_client import DatadogClient

    _DD_AVAILABLE = True
except ImportError:
    _DD_AVAILABLE = False
    DatadogClient = None  # type: ignore[assignment,misc]


class DatadogBackend:
    """Ships telemetry to Datadog via the API client.

    Wraps the lower-level ``DatadogClient`` so the rest of detra talks to
    the abstract ``TelemetryBackend`` protocol only.
    """

    def __init__(self, datadog_config):
        if not _DD_AVAILABLE:
            raise ImportError(
                "ddtrace and datadog-api-client required.  "
                "Install with: pip install detra[datadog]"
            )
        self._client = DatadogClient(datadog_config)
        self._base_tags = self._build_tags(datadog_config)

    # -- TelemetryBackend protocol -----------------------------------------

    async def emit_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        await self._submit("gauge", name, value, tags)

    async def emit_count(
        self, name: str, value: int, tags: dict[str, str] | None = None,
    ) -> None:
        await self._submit("count", name, value, tags)

    async def emit_distribution(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        await self._submit("gauge", name, value, tags)

    async def emit_event(
        self,
        title: str,
        text: str,
        level: str = "info",
        tags: dict[str, str] | None = None,
    ) -> None:
        level_map = {"error": "error", "warning": "warning", "critical": "error"}
        await self._client.submit_event(
            title=title,
            text=text,
            alert_type=level_map.get(level, "info"),
            tags=self._dd_tags(tags),
        )

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        await self._client.close()

    # -- public accessor for DD-specific features --------------------------

    @property
    def client(self) -> "DatadogClient":
        """Access the raw DatadogClient for DD-only operations (monitors, dashboards)."""
        return self._client

    # -- internals ---------------------------------------------------------

    async def _submit(
        self, metric_type: str, name: str, value: float, tags: dict[str, str] | None,
    ) -> None:
        await self._client.submit_metrics([
            {
                "metric": name,
                "type": metric_type,
                "points": [[time.time(), value]],
                "tags": self._dd_tags(tags),
            }
        ])

    def _dd_tags(self, tags: dict[str, str] | None) -> list[str]:
        out = list(self._base_tags)
        if tags:
            out.extend(f"{k}:{v}" for k, v in tags.items())
        return out

    @staticmethod
    def _build_tags(config) -> list[str]:
        tags: list[str] = []
        if getattr(config, "service", None):
            tags.append(f"service:{config.service}")
        if getattr(config, "env", None):
            tags.append(f"env:{config.env}")
        if getattr(config, "version", None):
            tags.append(f"version:{config.version}")
        return tags
