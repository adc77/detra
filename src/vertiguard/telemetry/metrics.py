"""Metrics submission utilities."""

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from vertiguard.telemetry.datadog_client import DatadogClient

logger = structlog.get_logger()


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    metric_type: str = "gauge"  # gauge, count, distribution
    tags: list[str] = field(default_factory=list)
    timestamp: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for submission."""
        return {
            "metric": self.name,
            "type": self.metric_type,
            "points": [[self.timestamp or time.time(), self.value]],
            "tags": self.tags,
        }


class MetricsSubmitter:
    """
    High-level interface for submitting VertiGuard metrics.

    Provides semantic methods for common metric types like
    latency, adherence scores, and flag counts.
    """

    def __init__(self, client: DatadogClient, app_name: str):
        """
        Initialize the metrics submitter.

        Args:
            client: Datadog client instance.
            app_name: Application name for tagging.
        """
        self.client = client
        self.app_name = app_name
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = 100

    async def submit_latency(
        self,
        node_name: str,
        latency_ms: float,
        span_kind: str = "workflow",
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit a latency metric.

        Args:
            node_name: Name of the traced node.
            latency_ms: Latency in milliseconds.
            span_kind: Type of span.
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [
            f"node:{node_name}",
            f"span_kind:{span_kind}",
            f"app:{self.app_name}",
        ]
        if additional_tags:
            tags.extend(additional_tags)

        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.node.latency",
                    "type": "distribution",
                    "points": [[time.time(), latency_ms]],
                    "tags": tags,
                }
            ]
        )

    async def submit_adherence_score(
        self,
        node_name: str,
        score: float,
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit an adherence score metric.

        Args:
            node_name: Name of the traced node.
            score: Adherence score (0.0 to 1.0).
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [f"node:{node_name}", f"app:{self.app_name}"]
        if additional_tags:
            tags.extend(additional_tags)

        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.node.adherence_score",
                    "type": "gauge",
                    "points": [[time.time(), score]],
                    "tags": tags,
                }
            ]
        )

    async def submit_call(
        self,
        node_name: str,
        status: str = "success",
        span_kind: str = "workflow",
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit a call count metric.

        Args:
            node_name: Name of the traced node.
            status: Call status (success, error).
            span_kind: Type of span.
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [
            f"node:{node_name}",
            f"status:{status}",
            f"span_kind:{span_kind}",
            f"app:{self.app_name}",
        ]
        if additional_tags:
            tags.extend(additional_tags)

        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.node.calls",
                    "type": "count",
                    "points": [[time.time(), 1]],
                    "tags": tags,
                }
            ]
        )

    async def submit_flag(
        self,
        node_name: str,
        category: Optional[str] = None,
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit a flag count metric.

        Args:
            node_name: Name of the traced node.
            category: Flag category.
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [f"node:{node_name}", f"app:{self.app_name}"]
        if category:
            tags.append(f"category:{category}")
        if additional_tags:
            tags.extend(additional_tags)

        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.node.flagged",
                    "type": "count",
                    "points": [[time.time(), 1]],
                    "tags": tags,
                }
            ]
        )

    async def submit_evaluation_metrics(
        self,
        node_name: str,
        eval_latency_ms: float,
        tokens_used: int,
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit evaluation-related metrics.

        Args:
            node_name: Name of the traced node.
            eval_latency_ms: Evaluation latency in milliseconds.
            tokens_used: Number of tokens used.
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [f"node:{node_name}", f"app:{self.app_name}"]
        if additional_tags:
            tags.extend(additional_tags)

        ts = time.time()
        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.evaluation.latency",
                    "type": "distribution",
                    "points": [[ts, eval_latency_ms]],
                    "tags": tags,
                },
                {
                    "metric": "vertiguard.evaluation.tokens",
                    "type": "count",
                    "points": [[ts, tokens_used]],
                    "tags": tags,
                },
            ]
        )

    async def submit_security_issue(
        self,
        node_name: str,
        check_type: str,
        severity: str,
        additional_tags: Optional[list[str]] = None,
    ) -> bool:
        """
        Submit a security issue metric.

        Args:
            node_name: Name of the traced node.
            check_type: Type of security check.
            severity: Issue severity.
            additional_tags: Extra tags to include.

        Returns:
            True if successful.
        """
        tags = [
            f"node:{node_name}",
            f"check:{check_type}",
            f"severity:{severity}",
            f"app:{self.app_name}",
        ]
        if additional_tags:
            tags.extend(additional_tags)

        return await self.client.submit_metrics(
            [
                {
                    "metric": "vertiguard.security.issues",
                    "type": "count",
                    "points": [[time.time(), 1]],
                    "tags": tags,
                }
            ]
        )

    def buffer_metric(self, metric: MetricPoint) -> None:
        """
        Add a metric to the buffer for batch submission.

        Args:
            metric: Metric point to buffer.
        """
        self._buffer.append(metric.to_dict())

    async def flush_buffer(self) -> bool:
        """
        Flush buffered metrics to Datadog.

        Returns:
            True if successful or buffer was empty.
        """
        if not self._buffer:
            return True

        metrics = self._buffer.copy()
        self._buffer.clear()

        return await self.client.submit_metrics(metrics)
