"""VertiGuard trace decorators for LLM observability."""

import asyncio
import functools
import time
from typing import Any, Callable, Optional, TypeVar

import structlog
from ddtrace.llmobs import LLMObs

from detra.config.loader import get_node_config
from detra.config.schema import NodeConfig
from detra.evaluation.engine import EvaluationEngine
from detra.evaluation.gemini_judge import EvaluationResult
from detra.telemetry.datadog_client import DatadogClient

logger = structlog.get_logger()

T = TypeVar("T")

# Module-level references set by client
_evaluation_engine: Optional[EvaluationEngine] = None
_datadog_client: Optional[DatadogClient] = None


def set_evaluation_engine(engine: EvaluationEngine) -> None:
    """Set the evaluation engine for decorators."""
    global _evaluation_engine
    _evaluation_engine = engine


def set_datadog_client(client: DatadogClient) -> None:
    """Set the Datadog client for decorators."""
    global _datadog_client
    _datadog_client = client


class VertiGuardTrace:
    """
    Decorator that wraps functions with:
    - Datadog LLM Observability tracing
    - Gemini-based adherence evaluation
    - Custom metrics submission
    - Automatic flagging and alerting
    """

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
        """
        Initialize the trace decorator.

        Args:
            node_name: Name of the node being traced.
            span_kind: Type of span (workflow, llm, task, agent).
            capture_input: Whether to capture input data.
            capture_output: Whether to capture output data.
            evaluate: Whether to run evaluation.
            input_extractor: Custom function to extract input data.
            output_extractor: Custom function to extract output data.
        """
        self.node_name = node_name
        self.span_kind = span_kind
        self.capture_input = capture_input
        self.capture_output = capture_output
        self.evaluate = evaluate
        self.input_extractor = input_extractor or self._default_input_extractor
        self.output_extractor = output_extractor or self._default_output_extractor

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Apply the decorator to a function."""
        if asyncio.iscoroutinefunction(func):
            return self._wrap_async(func)
        return self._wrap_sync(func)

    def _wrap_sync(self, func: Callable[..., T]) -> Callable[..., T]:
        """Wrap a synchronous function."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return asyncio.get_event_loop().run_until_complete(
                self._execute_async(func, args, kwargs)
            )
        return wrapper

    def _wrap_async(self, func: Callable[..., T]) -> Callable[..., T]:
        """Wrap an async function."""
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self._execute_async(func, args, kwargs)
        return wrapper

    async def _execute_async(
        self, func: Callable[..., T], args: tuple, kwargs: dict
    ) -> T:
        """Execute the wrapped function with tracing and evaluation."""
        start_time = time.time()
        node_config = get_node_config(self.node_name)

        input_data: Optional[Any] = None
        output_data: Optional[Any] = None
        error: Optional[Exception] = None
        eval_result: Optional[EvaluationResult] = None

        # Get span context manager
        span_cm = self._get_span_context()

        try:
            with span_cm as span:
                # Capture and annotate input
                if self.capture_input:
                    input_data = self.input_extractor(args, kwargs)
                    LLMObs.annotate(span=span, input_data=input_data)

                # Execute function
                if asyncio.iscoroutinefunction(func):
                    output_data = await func(*args, **kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    output_data = await loop.run_in_executor(
                        None, lambda: func(*args, **kwargs)
                    )

                # Capture and annotate output
                if self.capture_output and output_data is not None:
                    output_str = self.output_extractor(output_data)
                    LLMObs.annotate(span=span, output_data=output_str)

                # Run evaluation
                if self.evaluate and node_config and _evaluation_engine:
                    eval_result = await self._run_evaluation(
                        node_config, input_data, output_data, span
                    )

                # Submit metrics
                latency_ms = (time.time() - start_time) * 1000
                await self._submit_metrics(latency_ms, eval_result, error=None)

                return output_data

        except Exception as e:
            error = e
            latency_ms = (time.time() - start_time) * 1000
            await self._submit_metrics(latency_ms, eval_result, error=e)
            await self._submit_error_event(e, input_data)
            raise

    def _get_span_context(self):
        """Get the appropriate ddtrace span context manager."""
        span_methods = {
            "workflow": LLMObs.workflow,
            "llm": lambda name: LLMObs.llm(model_name="gemini", name=name),
            "task": LLMObs.task,
            "agent": LLMObs.agent,
        }
        return span_methods.get(self.span_kind, LLMObs.workflow)(self.node_name)

    async def _run_evaluation(
        self,
        node_config: NodeConfig,
        input_data: Any,
        output_data: Any,
        span: Any,
    ) -> Optional[EvaluationResult]:
        """Run the evaluation engine and submit results."""
        if not _evaluation_engine:
            return None

        try:
            eval_result = await _evaluation_engine.evaluate(
                node_config=node_config,
                input_data=input_data,
                output_data=output_data,
            )

            # Submit evaluation to LLMObs
            LLMObs.submit_evaluation(
                span=span,
                label="adherence_score",
                metric_type="score",
                value=eval_result.score,
            )

            if eval_result.flagged:
                LLMObs.submit_evaluation(
                    span=span,
                    label="flag_category",
                    metric_type="categorical",
                    value=eval_result.flag_category or "unknown",
                )

                # Submit flag event
                await self._submit_flag_event(eval_result, input_data, output_data)

            # Submit security issues
            for issue in eval_result.security_issues:
                if issue.get("detected"):
                    LLMObs.submit_evaluation(
                        span=span,
                        label=f"security_{issue['check']}",
                        metric_type="categorical",
                        value=issue.get("severity", "unknown"),
                    )

            return eval_result

        except Exception as e:
            logger.error("Evaluation failed", error=str(e), node=self.node_name)
            return None

    async def _submit_metrics(
        self,
        latency_ms: float,
        eval_result: Optional[EvaluationResult],
        error: Optional[Exception],
    ) -> None:
        """Submit custom metrics to Datadog."""
        if not _datadog_client:
            return

        base_tags = [f"node:{self.node_name}", f"span_kind:{self.span_kind}"]
        ts = time.time()

        metrics = [
            {
                "metric": "vertiguard.node.latency",
                "type": "distribution",
                "points": [[ts, latency_ms]],
                "tags": base_tags,
            },
            {
                "metric": "vertiguard.node.calls",
                "type": "count",
                "points": [[ts, 1]],
                "tags": base_tags + [f"status:{'error' if error else 'success'}"],
            },
        ]

        if eval_result:
            metrics.extend([
                {
                    "metric": "vertiguard.node.adherence_score",
                    "type": "gauge",
                    "points": [[ts, eval_result.score]],
                    "tags": base_tags,
                },
                {
                    "metric": "vertiguard.node.flagged",
                    "type": "count",
                    "points": [[ts, 1 if eval_result.flagged else 0]],
                    "tags": base_tags + (
                        [f"category:{eval_result.flag_category}"]
                        if eval_result.flag_category else []
                    ),
                },
                {
                    "metric": "vertiguard.evaluation.latency",
                    "type": "distribution",
                    "points": [[ts, eval_result.latency_ms]],
                    "tags": base_tags,
                },
                {
                    "metric": "vertiguard.evaluation.tokens",
                    "type": "count",
                    "points": [[ts, eval_result.eval_tokens_used]],
                    "tags": base_tags,
                },
            ])

            # Security metrics
            for issue in eval_result.security_issues:
                if issue.get("detected"):
                    metrics.append({
                        "metric": "vertiguard.security.issues",
                        "type": "count",
                        "points": [[ts, 1]],
                        "tags": base_tags + [
                            f"check:{issue['check']}",
                            f"severity:{issue.get('severity', 'unknown')}",
                        ],
                    })

        await _datadog_client.submit_metrics(metrics)

    async def _submit_flag_event(
        self,
        eval_result: EvaluationResult,
        input_data: Any,
        output_data: Any,
    ) -> None:
        """Submit a flag event to Datadog."""
        if not _datadog_client:
            return

        failed_checks_text = self._format_failed_checks(eval_result.checks_failed)

        text = f"""## Flag Details
- **Node:** {self.node_name}
- **Score:** {eval_result.score:.2f}
- **Category:** {eval_result.flag_category}
- **Reason:** {eval_result.flag_reason}

## Failed Checks
{failed_checks_text}

## Input Preview
```
{str(input_data)[:500]}
```

## Output Preview
```
{str(output_data)[:500]}
```
"""

        await _datadog_client.submit_event(
            title=f"VertiGuard Flag: {self.node_name}",
            text=text,
            alert_type="warning" if eval_result.score > 0.5 else "error",
            tags=[
                f"node:{self.node_name}",
                f"category:{eval_result.flag_category}",
                f"score:{eval_result.score:.2f}",
            ],
            aggregation_key=f"vertiguard-flag-{self.node_name}",
        )

    async def _submit_error_event(
        self, error: Exception, input_data: Any
    ) -> None:
        """Submit an error event."""
        if not _datadog_client:
            return

        await _datadog_client.submit_event(
            title=f"VertiGuard Error: {self.node_name}",
            text=f"```\n{str(error)}\n```\n\nInput: {str(input_data)[:300]}",
            alert_type="error",
            tags=[f"node:{self.node_name}", f"error_type:{type(error).__name__}"],
            aggregation_key=f"vertiguard-error-{self.node_name}",
        )

    def _format_failed_checks(self, checks: list) -> str:
        """Format failed checks for display."""
        if not checks:
            return "None"
        return "\n".join([f"- {c.behavior}: {c.reasoning}" for c in checks])

    @staticmethod
    def _default_input_extractor(args: tuple, kwargs: dict) -> str:
        """Default input extraction."""
        parts = []
        if args:
            parts.append(f"args: {args}")
        if kwargs:
            parts.append(f"kwargs: {kwargs}")
        return " | ".join(parts) if parts else "No input"

    @staticmethod
    def _default_output_extractor(output: Any) -> str:
        """Default output extraction."""
        return str(output) if output is not None else "No output"


# Convenience functions
def trace(node_name: str, **kwargs) -> VertiGuardTrace:
    """Create a trace decorator."""
    return VertiGuardTrace(node_name, span_kind="workflow", **kwargs)


def workflow(node_name: str, **kwargs) -> VertiGuardTrace:
    """Create a workflow trace decorator."""
    return VertiGuardTrace(node_name, span_kind="workflow", **kwargs)


def llm(node_name: str, **kwargs) -> VertiGuardTrace:
    """Create an LLM trace decorator."""
    return VertiGuardTrace(node_name, span_kind="llm", **kwargs)


def task(node_name: str, **kwargs) -> VertiGuardTrace:
    """Create a task trace decorator."""
    return VertiGuardTrace(node_name, span_kind="task", **kwargs)


def agent(node_name: str, **kwargs) -> VertiGuardTrace:
    """Create an agent trace decorator."""
    return VertiGuardTrace(node_name, span_kind="agent", **kwargs)
