"""Bridge to Datadog LLM Observability."""

import os
from contextlib import contextmanager
from typing import Any, Optional

import structlog
from ddtrace.llmobs import LLMObs

from detra.config.schema import VertiGuardConfig

logger = structlog.get_logger()


class LLMObsBridge:
    """
    Wrapper around ddtrace LLMObs for VertiGuard integration.

    Provides a clean interface for LLM Observability operations
    including span management, annotations, and evaluations.
    """

    def __init__(self, config: VertiGuardConfig):
        """
        Initialize the LLMObs bridge.

        Args:
            config: VertiGuard configuration.
        """
        self.config = config
        self._enabled = False

    def enable(self) -> None:
        """Enable LLM Observability."""
        if self._enabled:
            return

        try:
            # Set environment variables for ddtrace
            os.environ.setdefault("DD_API_KEY", self.config.datadog.api_key)
            os.environ.setdefault("DD_SITE", self.config.datadog.site)
            os.environ.setdefault("DD_LLMOBS_ENABLED", "1")
            os.environ.setdefault("DD_LLMOBS_ML_APP", self.config.app_name)
            os.environ.setdefault("DD_LLMOBS_AGENTLESS_ENABLED", "1")

            if self.config.datadog.env:
                os.environ.setdefault("DD_ENV", self.config.datadog.env)
            if self.config.datadog.service:
                os.environ.setdefault("DD_SERVICE", self.config.datadog.service)
            if self.config.datadog.version:
                os.environ.setdefault("DD_VERSION", self.config.datadog.version)

            LLMObs.enable(
                ml_app=self.config.app_name,
                api_key=self.config.datadog.api_key,
                site=self.config.datadog.site,
                agentless_enabled=True,
                env=self.config.datadog.env or self.config.environment.value,
                service=self.config.datadog.service,
                integrations_enabled=True,
            )

            self._enabled = True
            logger.info(
                "LLM Observability enabled",
                app_name=self.config.app_name,
                site=self.config.datadog.site,
            )

        except Exception as e:
            logger.error("Failed to enable LLM Observability", error=str(e))
            raise

    def disable(self) -> None:
        """Disable and flush LLM Observability."""
        if self._enabled:
            try:
                LLMObs.flush()
            except Exception as e:
                logger.warning("Error flushing LLMObs", error=str(e))
            self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if LLM Observability is enabled."""
        return self._enabled

    @staticmethod
    def annotate(
        span: Optional[Any] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Annotate a span with input/output data.

        Args:
            span: Span to annotate (current span if None).
            input_data: Input data to record.
            output_data: Output data to record.
            metadata: Additional metadata.
            tags: Additional tags.
        """
        try:
            LLMObs.annotate(
                span=span,
                input_data=input_data,
                output_data=output_data,
                metadata=metadata,
                tags=tags,
            )
        except Exception as e:
            logger.warning("Failed to annotate span", error=str(e))

    @staticmethod
    def submit_evaluation(
        span: Optional[Any] = None,
        label: Optional[str] = None,
        metric_type: str = "score",
        value: Optional[Any] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Submit an evaluation metric for a span.

        Args:
            span: Span to evaluate (current span if None).
            label: Evaluation label.
            metric_type: Type of metric (score, categorical).
            value: Metric value.
            tags: Additional tags.
        """
        try:
            LLMObs.submit_evaluation(
                span=span,
                label=label,
                metric_type=metric_type,
                value=value,
                tags=tags,
            )
        except Exception as e:
            logger.warning("Failed to submit evaluation", error=str(e))

    @staticmethod
    @contextmanager
    def workflow(name: str):
        """
        Create a workflow span context manager.

        Args:
            name: Workflow name.

        Yields:
            The workflow span.
        """
        with LLMObs.workflow(name) as span:
            yield span

    @staticmethod
    @contextmanager
    def llm(model_name: str, name: Optional[str] = None, model_provider: Optional[str] = None):
        """
        Create an LLM span context manager.

        Args:
            model_name: Name of the LLM model.
            name: Span name.
            model_provider: Model provider name.

        Yields:
            The LLM span.
        """
        with LLMObs.llm(
            model_name=model_name,
            name=name,
            model_provider=model_provider,
        ) as span:
            yield span

    @staticmethod
    @contextmanager
    def task(name: str):
        """
        Create a task span context manager.

        Args:
            name: Task name.

        Yields:
            The task span.
        """
        with LLMObs.task(name) as span:
            yield span

    @staticmethod
    @contextmanager
    def agent(name: str):
        """
        Create an agent span context manager.

        Args:
            name: Agent name.

        Yields:
            The agent span.
        """
        with LLMObs.agent(name) as span:
            yield span

    @staticmethod
    def flush() -> None:
        """Flush all pending data."""
        try:
            LLMObs.flush()
        except Exception as e:
            logger.warning("Error flushing LLMObs", error=str(e))

    @staticmethod
    def export_span(span: Optional[Any] = None) -> Optional[dict]:
        """
        Export span context for distributed tracing.

        Args:
            span: Span to export (current span if None).

        Returns:
            Span context dictionary.
        """
        try:
            return LLMObs.export_span(span=span)
        except Exception as e:
            logger.warning("Failed to export span", error=str(e))
            return None
