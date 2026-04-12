"""Telemetry backend protocol -- implement this to ship metrics anywhere."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TelemetryBackend(Protocol):
    """Structural interface every telemetry backend must satisfy.

    Implementations ship metrics/events to their respective systems.
    Any object with the right method signatures works -- no inheritance required.
    """

    async def emit_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None: ...

    async def emit_count(
        self, name: str, value: int, tags: dict[str, str] | None = None,
    ) -> None: ...

    async def emit_distribution(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None: ...

    async def emit_event(
        self,
        title: str,
        text: str,
        level: str = "info",
        tags: dict[str, str] | None = None,
    ) -> None: ...

    async def flush(self) -> None: ...

    async def close(self) -> None: ...
