"""Trace decorators for LLM guardrails and observability.

Decorators capture latency, optionally evaluate outputs against a
behavior spec via the configured Judge, and ship metrics through
whichever TelemetryBackend is active.
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, TypeVar

import structlog

from detra.backends.base import TelemetryBackend
from detra.config.schema import SamplingConfig
from detra.judges.base import EvaluationResult

logger = structlog.get_logger()

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Module-level state (wired by ``Detra.__init__``)
# ---------------------------------------------------------------------------

_backend: Optional[TelemetryBackend] = None
_engine: Optional[Any] = None  # EvaluationEngine -- avoid circular import
_sampling: SamplingConfig = SamplingConfig()


def set_backend(backend: TelemetryBackend) -> None:
    global _backend
    _backend = backend


def set_evaluation_engine(engine) -> None:
    global _engine
    _engine = engine


def set_sampling_config(config: SamplingConfig) -> None:
    global _sampling
    _sampling = config


def _should_evaluate() -> bool:
    return random.random() < _sampling.rate


# ---------------------------------------------------------------------------
# Core decorator class
# ---------------------------------------------------------------------------


class DetraTrace:
    """Decorator that wraps functions with telemetry + evaluation."""

    def __init__(
        self,
        node_name: str,
        span_kind: str = "workflow",
        capture_input: bool = True,
        capture_output: bool = True,
        evaluate: bool = True,
        input_extractor: Optional[Callable[..., Any]] = None,
        output_extractor: Optional[Callable[[Any], str]] = None,
    ):
        self.node_name = node_name
        self.span_kind = span_kind
        self.capture_input = capture_input
        self.capture_output = capture_output
        self.evaluate = evaluate
        self.input_extractor = input_extractor or _default_input_extractor
        self.output_extractor = output_extractor or _default_output_extractor

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            return self._wrap_async(func)
        return self._wrap_sync(func)

    # -- async path --------------------------------------------------------

    def _wrap_async(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self._execute(func, args, kwargs, is_async=True)

        return wrapper  # type: ignore[return-value]

    # -- sync path (the old one crashed inside a running loop) -------------

    def _wrap_sync(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                asyncio.get_running_loop()
                # A loop is already running (e.g. FastAPI) -- fall back to
                # a lightweight sync-only path that doesn't nest asyncio.run.
                return self._execute_sync(func, args, kwargs)
            except RuntimeError:
                # No running loop -- safe to use asyncio.run.
                return asyncio.run(self._execute(func, args, kwargs, is_async=False))

        return wrapper  # type: ignore[return-value]

    # -- execution ---------------------------------------------------------

    async def _execute(
        self, func: Callable, args: tuple, kwargs: dict, *, is_async: bool,
    ) -> Any:
        start = time.time()
        tags = {"node": self.node_name, "span_kind": self.span_kind}

        input_data = self.input_extractor(args, kwargs) if self.capture_input else None
        eval_result: Optional[EvaluationResult] = None

        try:
            output_data = (await func(*args, **kwargs)) if is_async else func(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000

            if self.evaluate and _engine and _should_evaluate():
                eval_result = await self._run_eval(input_data, output_data)

            await self._emit(latency_ms, eval_result, tags, error=None)

            if eval_result and eval_result.flagged:
                await self._emit_flag(eval_result, input_data, output_data, tags)

            return output_data

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            await self._emit(latency_ms, None, tags, error=e)
            raise

    def _execute_sync(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Sync fallback when called from inside an already-running loop."""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000
            self._fire_and_forget(
                self._emit(
                    latency_ms,
                    None,
                    {"node": self.node_name, "span_kind": self.span_kind},
                    error=None,
                )
            )
            return result
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self._fire_and_forget(
                self._emit(
                    latency_ms,
                    None,
                    {"node": self.node_name, "span_kind": self.span_kind},
                    error=e,
                )
            )
            raise

    # -- evaluation --------------------------------------------------------

    async def _run_eval(self, input_data: Any, output_data: Any) -> Optional[EvaluationResult]:
        from detra.config.loader import get_node_config

        node_config = get_node_config(self.node_name)
        if not node_config:
            return None
        try:
            return await _engine.evaluate(
                node_config=node_config,
                input_data=input_data,
                output_data=output_data,
            )
        except Exception as e:
            logger.error("Evaluation failed", error=str(e), node=self.node_name)
            return None

    # -- telemetry ---------------------------------------------------------

    async def _emit(
        self,
        latency_ms: float,
        eval_result: Optional[EvaluationResult],
        tags: dict[str, str],
        *,
        error: Optional[Exception],
    ) -> None:
        if not _backend:
            return

        await _backend.emit_distribution("detra.node.latency_ms", latency_ms, tags)
        await _backend.emit_count(
            "detra.node.calls", 1,
            {**tags, "status": "error" if error else "success"},
        )

        if eval_result:
            await _backend.emit_gauge("detra.eval.score", eval_result.score, tags)
            await _backend.emit_count(
                "detra.eval.flagged", 1 if eval_result.flagged else 0, tags,
            )
            if eval_result.latency_ms:
                await _backend.emit_distribution(
                    "detra.eval.latency_ms", eval_result.latency_ms, tags,
                )
            if eval_result.eval_tokens_used:
                await _backend.emit_count(
                    "detra.eval.tokens", eval_result.eval_tokens_used, tags,
                )

    async def _emit_flag(
        self,
        eval_result: EvaluationResult,
        input_data: Any,
        output_data: Any,
        tags: dict[str, str],
    ) -> None:
        if not _backend:
            return

        failed = "\n".join(
            f"- {c.behavior}: {c.reasoning}" for c in eval_result.checks_failed
        )
        text = (
            f"Score: {eval_result.score:.2f}\n"
            f"Category: {eval_result.flag_category}\n"
            f"Reason: {eval_result.flag_reason}\n"
            f"Failed checks:\n{failed}"
        )
        level = "error" if eval_result.score < 0.5 else "warning"
        flag_tags = dict(tags)
        if eval_result.flag_category:
            flag_tags["category"] = eval_result.flag_category

        await _backend.emit_event(
            title=f"detra flag: {self.node_name}",
            text=text,
            level=level,
            tags=flag_tags,
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _fire_and_forget(coro) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Default extractors
# ---------------------------------------------------------------------------

def _default_input_extractor(args: tuple, kwargs: dict) -> str:
    parts = []
    if args:
        parts.append(str(args))
    if kwargs:
        parts.append(str(kwargs))
    return " | ".join(parts) if parts else "no input"


def _default_output_extractor(output: Any) -> str:
    return str(output) if output is not None else "no output"


# ---------------------------------------------------------------------------
# Public convenience factories
# ---------------------------------------------------------------------------

def trace(node_name: str, **kw) -> DetraTrace:
    return DetraTrace(node_name, span_kind="workflow", **kw)


def workflow(node_name: str, **kw) -> DetraTrace:
    return DetraTrace(node_name, span_kind="workflow", **kw)


def llm(node_name: str, **kw) -> DetraTrace:
    return DetraTrace(node_name, span_kind="llm", **kw)


def task(node_name: str, **kw) -> DetraTrace:
    return DetraTrace(node_name, span_kind="task", **kw)


def agent(node_name: str, **kw) -> DetraTrace:
    return DetraTrace(node_name, span_kind="agent", **kw)
