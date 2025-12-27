"""Structured logging configuration and utilities."""

import logging
import sys
from typing import Any, Optional

import structlog


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    add_timestamps: bool = True,
) -> None:
    """
    Configure structured logging for VertiGuard.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_format: Whether to output JSON format (for production).
        add_timestamps: Whether to add timestamps to logs.
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Build processor chain
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
    ]

    if add_timestamps:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))

    processors.extend(
        [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]
    )

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class StructuredLogger:
    """
    VertiGuard-specific structured logger with context management.

    Provides methods for logging with consistent context across
    all VertiGuard operations.
    """

    def __init__(self, name: str, app_name: Optional[str] = None):
        """
        Initialize the structured logger.

        Args:
            name: Logger name (typically module name).
            app_name: Application name for context.
        """
        self._logger = structlog.get_logger(name)
        self._app_name = app_name

    def _add_context(self, **kwargs: Any) -> dict[str, Any]:
        """Add standard context to log entries."""
        if self._app_name:
            kwargs["app"] = self._app_name
        return kwargs

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._logger.debug(message, **self._add_context(**kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._logger.info(message, **self._add_context(**kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(message, **self._add_context(**kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._logger.error(message, **self._add_context(**kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        self._logger.exception(message, **self._add_context(**kwargs))

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """
        Create a new logger with bound context.

        Args:
            **kwargs: Context to bind.

        Returns:
            New logger with bound context.
        """
        new_logger = StructuredLogger(
            name=self._logger._logger.name if hasattr(self._logger, '_logger') else "vertiguard",
            app_name=self._app_name,
        )
        new_logger._logger = self._logger.bind(**kwargs)
        return new_logger

    def node_context(self, node_name: str, span_kind: str = "workflow") -> "StructuredLogger":
        """
        Create a logger bound to a specific node context.

        Args:
            node_name: Name of the node.
            span_kind: Type of span.

        Returns:
            Logger with node context.
        """
        return self.bind(node=node_name, span_kind=span_kind)

    def evaluation_context(
        self, node_name: str, score: Optional[float] = None
    ) -> "StructuredLogger":
        """
        Create a logger bound to an evaluation context.

        Args:
            node_name: Name of the node being evaluated.
            score: Evaluation score if available.

        Returns:
            Logger with evaluation context.
        """
        ctx = {"node": node_name, "context": "evaluation"}
        if score is not None:
            ctx["score"] = score
        return self.bind(**ctx)


def get_logger(name: str = "vertiguard", app_name: Optional[str] = None) -> StructuredLogger:
    """
    Get a VertiGuard structured logger.

    Args:
        name: Logger name.
        app_name: Application name for context.

    Returns:
        Configured StructuredLogger instance.
    """
    return StructuredLogger(name, app_name)
