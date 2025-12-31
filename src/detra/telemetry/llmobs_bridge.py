"""Bridge to Datadog LLM Observability."""

import os
import ssl
from contextlib import contextmanager
from typing import Any, Optional

import structlog
from ddtrace.llmobs import LLMObs

from detra.config.schema import detraConfig

try:
    import certifi
    CERTIFI_AVAILABLE = True
except ImportError:
    CERTIFI_AVAILABLE = False

logger = structlog.get_logger()


class LLMObsBridge:
    """Wrapper around ddtrace LLMObs for detra integration."""

    def __init__(self, config: detraConfig):
        """Initialize the LLMObs bridge."""
        self.config = config
        self._enabled = False

    def enable(self) -> None:
        """Enable LLM Observability in agentless mode."""
        if self._enabled:
            return

        try:
            self._configure_ssl()

            site = self.config.datadog.site or "datadoghq.com"

            os.environ.setdefault("DD_API_KEY", self.config.datadog.api_key)
            os.environ.setdefault("DD_SITE", site)
            os.environ.setdefault("DD_LLMOBS_ENABLED", "1")
            os.environ.setdefault("DD_LLMOBS_ML_APP", self.config.app_name)
            os.environ.setdefault("DD_LLMOBS_AGENTLESS_ENABLED", "1")
            os.environ.setdefault("DD_TRACE_ENABLED", "false")
            os.environ.setdefault("DD_INSTRUMENTATION_TELEMETRY_ENABLED", "false")
            os.environ.setdefault("DD_AGENT_HOST", "")

            if self.config.datadog.env:
                os.environ.setdefault("DD_ENV", self.config.datadog.env)
            if self.config.datadog.service:
                os.environ.setdefault("DD_SERVICE", self.config.datadog.service)
            if self.config.datadog.version:
                os.environ.setdefault("DD_VERSION", self.config.datadog.version)

            LLMObs.enable(
                ml_app=self.config.app_name,
                api_key=self.config.datadog.api_key,
                site=site,
                agentless_enabled=True,
                env=self.config.datadog.env or self.config.environment.value,
                service=self.config.datadog.service,
                integrations_enabled=False,
            )

            self._enabled = True
            logger.info(
                "LLM Observability enabled",
                app_name=self.config.app_name,
                site=site,
                mode="agentless",
            )

        except Exception as e:
            logger.error("Failed to enable LLM Observability", error=str(e))
            raise

    def _configure_ssl(self) -> None:
        """Configure SSL context for ddtrace HTTP connections."""
        if not self.config.datadog.verify_ssl:
            ssl._create_default_https_context = ssl._create_unverified_context
            logger.warning("SSL verification disabled - not recommended for production")
        elif CERTIFI_AVAILABLE:
            try:
                cert_path = certifi.where()
                def create_context():
                    return ssl.create_default_context(cafile=cert_path)
                ssl._create_default_https_context = create_context
                logger.debug("Configured SSL context with certifi", path=cert_path)
            except Exception as e:
                logger.warning("Failed to configure SSL context with certifi", error=str(e))
        elif self.config.datadog.ssl_cert_path:
            try:
                cert_path = self.config.datadog.ssl_cert_path
                def create_context():
                    return ssl.create_default_context(cafile=cert_path)
                ssl._create_default_https_context = create_context
                logger.debug("Configured SSL context with custom certificate", path=cert_path)
            except Exception as e:
                logger.warning("Failed to configure SSL context with custom certificate", error=str(e))
        else:
            logger.warning("No SSL certificate bundle specified. Install 'certifi' for better compatibility.")

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
        """Annotate a span with input/output data."""
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
        """Submit an evaluation metric for a span."""
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
        """Create a workflow span context manager."""
        with LLMObs.workflow(name) as span:
            yield span

    @staticmethod
    @contextmanager
    def llm(model_name: str, name: Optional[str] = None, model_provider: Optional[str] = None):
        """Create an LLM span context manager."""
        with LLMObs.llm(
            model_name=model_name,
            name=name,
            model_provider=model_provider,
        ) as span:
            yield span

    @staticmethod
    @contextmanager
    def task(name: str):
        """Create a task span context manager."""
        with LLMObs.task(name) as span:
            yield span

    @staticmethod
    @contextmanager
    def agent(name: str):
        """Create an agent span context manager."""
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
        """Export span context for distributed tracing."""
        try:
            return LLMObs.export_span(span=span)
        except Exception as e:
            logger.warning("Failed to export span", error=str(e))
            return None
