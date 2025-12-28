"""Trace context and span utilities."""

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

import structlog
from ddtrace.llmobs import LLMObs

logger = structlog.get_logger()


@dataclass
class SpanContext:
    """Context for a traced span."""

    name: str
    span_kind: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    error: Optional[Exception] = None

    @property
    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def finish(self) -> None:
        """Mark the span as finished."""
        self.end_time = time.time()


class TraceManager:
    """
    Manages trace context and span operations.

    Provides utilities for creating and managing spans
    with proper context propagation.
    """

    def __init__(self, app_name: str):
        """
        Initialize the trace manager.

        Args:
            app_name: Application name for context.
        """
        self.app_name = app_name
        self._active_spans: dict[str, SpanContext] = {}

    @asynccontextmanager
    async def span(
        self,
        name: str,
        span_kind: str = "workflow",
        capture_input: bool = True,
        capture_output: bool = True,
    ) -> AsyncGenerator[SpanContext, None]:
        """
        Create a traced span context.

        Args:
            name: Span name.
            span_kind: Type of span (workflow, llm, task, agent).
            capture_input: Whether to capture input data.
            capture_output: Whether to capture output data.

        Yields:
            SpanContext for the active span.
        """
        context = SpanContext(name=name, span_kind=span_kind)

        # Get appropriate LLMObs context manager
        span_cm = self._get_llmobs_span(name, span_kind)

        try:
            with span_cm as llm_span:
                self._active_spans[name] = context

                yield context

                # Annotate span with captured data
                if capture_input and context.input_data is not None:
                    LLMObs.annotate(span=llm_span, input_data=context.input_data)
                if capture_output and context.output_data is not None:
                    LLMObs.annotate(span=llm_span, output_data=context.output_data)
                if context.metadata:
                    LLMObs.annotate(span=llm_span, metadata=context.metadata)
                if context.tags:
                    LLMObs.annotate(span=llm_span, tags=context.tags)

        except Exception as e:
            context.error = e
            raise
        finally:
            context.finish()
            self._active_spans.pop(name, None)

    def _get_llmobs_span(self, name: str, span_kind: str):
        """Get the appropriate LLMObs span context manager."""
        if span_kind == "llm":
            return LLMObs.llm(model_name="gemini", name=name)
        elif span_kind == "task":
            return LLMObs.task(name)
        elif span_kind == "agent":
            return LLMObs.agent(name)
        else:
            return LLMObs.workflow(name)

    def get_active_span(self, name: str) -> Optional[SpanContext]:
        """
        Get an active span by name.

        Args:
            name: Span name.

        Returns:
            SpanContext if found, None otherwise.
        """
        return self._active_spans.get(name)

    @staticmethod
    def annotate_current(
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Annotate the current active span.

        Args:
            input_data: Input data to record.
            output_data: Output data to record.
            metadata: Additional metadata.
            tags: Additional tags.
        """
        try:
            LLMObs.annotate(
                input_data=input_data,
                output_data=output_data,
                metadata=metadata,
                tags=tags,
            )
        except Exception as e:
            logger.warning("Failed to annotate current span", error=str(e))

    @staticmethod
    def submit_evaluation(
        label: str,
        value: Any,
        metric_type: str = "score",
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Submit an evaluation for the current span.

        Args:
            label: Evaluation label.
            value: Evaluation value.
            metric_type: Type of metric.
            tags: Additional tags.
        """
        try:
            LLMObs.submit_evaluation(
                label=label,
                metric_type=metric_type,
                value=value,
                tags=tags,
            )
        except Exception as e:
            logger.warning("Failed to submit evaluation", error=str(e))


def create_trace_id() -> str:
    """
    Generate a unique trace ID.

    Returns:
        Unique trace identifier.
    """
    import uuid

    return str(uuid.uuid4())


def extract_trace_context() -> Optional[dict[str, str]]:
    """
    Extract current trace context for propagation.

    Returns:
        Trace context dictionary or None.
    """
    try:
        return LLMObs.export_span()
    except Exception:
        return None
