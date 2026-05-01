"""Console backend -- prints telemetry to stderr. Zero extra deps."""

from __future__ import annotations

import sys
from typing import Any


class ConsoleBackend:
    """Writes human-readable metric lines to a stream (default stderr).

    Useful for local development and CI where you want to see what detra
    is doing without standing up a full telemetry pipeline.
    """

    def __init__(self, app_name: str, *, stream=None):
        self.app_name = app_name
        self._stream = stream or sys.stderr

    # -- TelemetryBackend protocol -----------------------------------------

    async def emit_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        self._write("GAUGE", name, value, tags)

    async def emit_count(
        self, name: str, value: int, tags: dict[str, str] | None = None,
    ) -> None:
        self._write("COUNT", name, value, tags)

    async def emit_distribution(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        self._write("DIST", name, value, tags)

    async def emit_event(
        self,
        title: str,
        text: str,
        level: str = "info",
        tags: dict[str, str] | None = None,
    ) -> None:
        tag_str = _fmt_tags(tags)
        self._stream.write(f"[detra|{level.upper()}] {title} {tag_str}\n")
        if text and level in ("error", "warning", "critical"):
            for line in text.split("\n")[:8]:
                self._stream.write(f"  {line}\n")

    async def flush(self) -> None:
        self._stream.flush()

    async def close(self) -> None:
        await self.flush()

    # -- internals ---------------------------------------------------------

    def _write(self, kind: str, name: str, value: Any, tags: dict[str, str] | None) -> None:
        self._stream.write(f"[detra|{kind}] {name}={value} {_fmt_tags(tags)}\n")


def _fmt_tags(tags: dict[str, str] | None) -> str:
    if not tags:
        return ""
    return " ".join(f"{k}={v}" for k, v in tags.items())
