"""OpenTelemetry backend -- emits metrics and span-events via the OTel SDK.

Follows the GenAI semantic conventions (gen_ai.*) where applicable and
falls back to detra.* for domain-specific metrics.

Requires: pip install detra[otel]
"""

from __future__ import annotations

from typing import Any

import structlog

try:
    from opentelemetry import metrics, trace

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

logger = structlog.get_logger()


class OTelBackend:
    """Ships telemetry through the OpenTelemetry API.

    Users are expected to configure their own exporters (OTLP, Prometheus,
    Jaeger, etc.) before initializing this backend.  OTelBackend creates a
    Meter and Tracer under the ``detra`` instrumentation scope and lazily
    builds instruments on first use.
    """

    def __init__(self, app_name: str, *, service_name: str | None = None):
        if not _OTEL_AVAILABLE:
            raise ImportError(
                "opentelemetry packages required.  Install with: pip install detra[otel]"
            )

        self.app_name = app_name
        self._service = service_name or app_name
        self._meter = metrics.get_meter("detra", "0.2.0")
        self._tracer = trace.get_tracer("detra", "0.2.0")

        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._up_down_counters: dict[str, Any] = {}
        self._gauge_last: dict[str, float] = {}

    # -- TelemetryBackend protocol -----------------------------------------

    async def emit_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        attrs = self._attrs(tags)
        # UpDownCounter needs a delta, not an absolute value.
        # Track last emitted value per (name, sorted-tags) and add the diff.
        key = (name, tuple(sorted((tags or {}).items())))
        prev = self._gauge_last.get(key, 0.0)
        delta = value - prev
        self._gauge_last[key] = value
        self._udc(name).add(delta, attributes=attrs)

    async def emit_count(
        self, name: str, value: int, tags: dict[str, str] | None = None,
    ) -> None:
        self._counter(name).add(value, attributes=self._attrs(tags))

    async def emit_distribution(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        self._histogram(name).record(value, attributes=self._attrs(tags))

    async def emit_event(
        self,
        title: str,
        text: str,
        level: str = "info",
        tags: dict[str, str] | None = None,
    ) -> None:
        with self._tracer.start_as_current_span("detra.event") as span:
            span.set_attribute("detra.event.title", title)
            span.set_attribute("detra.event.level", level)
            span.set_attribute("detra.event.text", text[:4096])
            for k, v in (tags or {}).items():
                span.set_attribute(f"detra.{k}", v)

    async def flush(self) -> None:
        for provider in (metrics.get_meter_provider(), trace.get_tracer_provider()):
            force_flush = getattr(provider, "force_flush", None)
            if callable(force_flush):
                try:
                    force_flush()
                except Exception as e:
                    logger.warning("OpenTelemetry force_flush failed", error=str(e))

    async def close(self) -> None:
        await self.flush()
        for provider in (metrics.get_meter_provider(), trace.get_tracer_provider()):
            shutdown = getattr(provider, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as e:
                    logger.warning("OpenTelemetry shutdown failed", error=str(e))

    # -- instrument factories (lazy) ---------------------------------------

    def _counter(self, name: str):
        if name not in self._counters:
            self._counters[name] = self._meter.create_counter(name)
        return self._counters[name]

    def _histogram(self, name: str):
        if name not in self._histograms:
            self._histograms[name] = self._meter.create_histogram(name)
        return self._histograms[name]

    def _udc(self, name: str):
        if name not in self._up_down_counters:
            self._up_down_counters[name] = self._meter.create_up_down_counter(name)
        return self._up_down_counters[name]

    @staticmethod
    def _attrs(tags: dict[str, str] | None) -> dict[str, str]:
        return tags or {}
