"""Sentry-style error tracking for catching and monitoring all application errors."""

import traceback
from typing import Any, Optional, Dict, List
from datetime import datetime
import hashlib
import structlog
import asyncio

from detra.telemetry.datadog_client import DatadogClient
from detra.errors.context import ErrorContext
from detra.errors.grouper import ErrorGrouper

logger = structlog.get_logger()


class ErrorTracker:
    """
    Comprehensive error tracking system (similar to Sentry).

    Features:
    - Automatic exception capture
    - Stack trace recording
    - Error grouping and deduplication
    - Breadcrumb tracking (events leading to error)
    - User context
    - Environment context
    - Error frequency tracking
    - Automatic Datadog incident creation

    Usage:
        tracker = ErrorTracker(datadog_client)

        # Automatic capture
        with tracker.capture():
            risky_operation()

        # Manual capture
        try:
            operation()
        except Exception as e:
            tracker.capture_exception(e, context={"user_id": "123"})
    """

    def __init__(
        self,
        datadog_client: DatadogClient,
        environment: str = "production",
        release: Optional[str] = None,
    ):
        """
        Initialize error tracker.

        Args:
            datadog_client: Datadog client for sending errors.
            environment: Environment name (production, staging, dev).
            release: Release version/tag.
        """
        self.datadog = datadog_client
        self.environment = environment
        self.release = release
        self.grouper = ErrorGrouper()

        # Error storage (in-memory, can be moved to DB)
        self._errors: Dict[str, List[Dict[str, Any]]] = {}
        self._breadcrumbs: List[Dict[str, Any]] = []
        self._user_context: Dict[str, Any] = {}

        # Statistics
        self.total_errors = 0
        self.unique_errors = 0

    def capture_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        level: str = "error",
        tags: Optional[List[str]] = None,
        user_info: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Capture an exception with full context.

        Args:
            exception: The exception to capture.
            context: Additional context about the error.
            level: Error level (error, warning, critical, info).
            tags: Tags for categorization.
            user_info: User information (id, email, username).
            extra: Extra metadata.

        Returns:
            Error ID (hash) for tracking.
        """
        # Extract stack trace
        tb = traceback.extract_tb(exception.__traceback__)
        stack_trace = "".join(traceback.format_exception(
            type(exception), exception, exception.__traceback__
        ))

        # Build error context
        error_context = ErrorContext(
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            stack_trace=stack_trace,
            traceback_frames=self._format_traceback(tb),
            breadcrumbs=self._breadcrumbs.copy(),
            context=context or {},
            user_info=user_info or self._user_context,
            extra=extra or {},
            environment=self.environment,
            release=self.release,
            timestamp=datetime.now().isoformat(),
        )

        # Group similar errors
        error_id = self.grouper.get_error_id(error_context)

        # Store error
        if error_id not in self._errors:
            self._errors[error_id] = []
            self.unique_errors += 1

        self._errors[error_id].append(error_context.to_dict())
        self.total_errors += 1

        # Log structured error
        logger.error(
            "Error captured",
            error_id=error_id,
            exception_type=error_context.exception_type,
            message=error_context.exception_message,
            level=level,
            total_occurrences=len(self._errors[error_id]),
        )

        # Submit to Datadog (fire-and-forget to avoid blocking)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._submit_to_datadog(error_context, error_id, level, tags))
            else:
                loop.run_until_complete(self._submit_to_datadog(error_context, error_id, level, tags))
        except Exception:
            pass  # Don't fail error capture if telemetry fails

        # Create incident for critical errors
        if level == "critical" or len(self._errors[error_id]) > 10:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._create_incident(error_context, error_id))
                else:
                    loop.run_until_complete(self._create_incident(error_context, error_id))
            except Exception:
                pass

        return error_id

    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Capture a message without an exception.

        Args:
            message: The message to capture.
            level: Message level (info, warning, error).
            context: Additional context.
            tags: Tags for categorization.

        Returns:
            Message ID.
        """
        error_context = ErrorContext(
            exception_type="Message",
            exception_message=message,
            context=context or {},
            environment=self.environment,
            release=self.release,
            timestamp=datetime.now().isoformat(),
        )

        message_id = hashlib.md5(message.encode()).hexdigest()[:12]

        logger.info(
            "Message captured",
            message=message,
            level=level,
            message_id=message_id,
        )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._submit_to_datadog(error_context, message_id, level, tags))
            else:
                loop.run_until_complete(self._submit_to_datadog(error_context, message_id, level, tags))
        except Exception:
            pass

        return message_id

    def add_breadcrumb(
        self,
        message: str,
        category: str = "default",
        level: str = "info",
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Add a breadcrumb (event leading up to an error).

        Args:
            message: Breadcrumb message.
            category: Category (navigation, http, user_action, etc.).
            level: Severity level.
            data: Additional data.
        """
        breadcrumb = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "category": category,
            "level": level,
            "data": data or {},
        }

        # Keep only last 100 breadcrumbs
        self._breadcrumbs.append(breadcrumb)
        if len(self._breadcrumbs) > 100:
            self._breadcrumbs.pop(0)

    def set_user(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs,
    ):
        """
        Set user context for future errors.

        Args:
            user_id: User ID.
            email: User email.
            username: Username.
            **kwargs: Additional user attributes.
        """
        self._user_context = {
            "id": user_id,
            "email": email,
            "username": username,
            **kwargs,
        }

    def capture(self):
        """
        Context manager for automatic exception capture.

        Usage:
            with error_tracker.capture():
                risky_operation()
        """
        return ErrorCaptureContext(self)

    def get_error_summary(self, error_id: str) -> Dict[str, Any]:
        """
        Get summary for a specific error group.

        Args:
            error_id: Error ID.

        Returns:
            Error summary with count, first/last seen, etc.
        """
        if error_id not in self._errors:
            return {}

        errors = self._errors[error_id]
        first_error = errors[0]
        last_error = errors[-1]

        return {
            "error_id": error_id,
            "count": len(errors),
            "first_seen": first_error["timestamp"],
            "last_seen": last_error["timestamp"],
            "exception_type": first_error["exception_type"],
            "exception_message": first_error["exception_message"],
            "users_affected": len(set(
                e.get("user_info", {}).get("id")
                for e in errors
                if e.get("user_info", {}).get("id")
            )),
        }

    def get_all_errors(self) -> List[Dict[str, Any]]:
        """Get all error summaries."""
        return [
            self.get_error_summary(error_id)
            for error_id in self._errors.keys()
        ]

    def clear_breadcrumbs(self):
        """Clear all breadcrumbs."""
        self._breadcrumbs.clear()

    def _format_traceback(self, tb) -> List[Dict[str, Any]]:
        """Format traceback into structured frames."""
        frames = []
        for frame in tb:
            frames.append({
                "filename": frame.filename,
                "line": frame.lineno,
                "function": frame.name,
                "code": frame.line,
            })
        return frames

    async def _submit_to_datadog(
        self,
        error_context: ErrorContext,
        error_id: str,
        level: str,
        tags: Optional[List[str]],
    ):
        """Submit error to Datadog as event."""
        try:
            # Create Datadog event
            await self.datadog.submit_event(
                title=f"Error: {error_context.exception_type}",
                text=f"""## {error_context.exception_message}

**Error ID**: `{error_id}`
**Environment**: {error_context.environment}
**Release**: {error_context.release or 'N/A'}

### Stack Trace
```
{error_context.stack_trace[:1000]}
```

### Context
{error_context.context}

### Recent Breadcrumbs
{self._format_breadcrumbs(error_context.breadcrumbs[-5:])}
""",
                alert_type=self._level_to_alert_type(level),
                tags=[
                    f"error_id:{error_id}",
                    f"exception_type:{error_context.exception_type}",
                    f"environment:{error_context.environment}",
                    *(tags or []),
                ],
            )

            # Submit metric
            await self.datadog.submit_metrics([
                {
                    "metric": "detra.errors.count",
                    "type": "count",
                    "points": [[int(datetime.now().timestamp()), 1]],
                    "tags": [
                        f"error_id:{error_id}",
                        f"exception_type:{error_context.exception_type}",
                        f"level:{level}",
                    ],
                }
            ])

        except Exception as e:
            logger.error("Failed to submit error to Datadog", error=str(e))

    async def _create_incident(
        self,
        error_context: ErrorContext,
        error_id: str,
    ):
        """Create Datadog incident for critical errors."""
        try:
            summary = self.get_error_summary(error_id)

            await self.datadog.create_incident(
                title=f"Critical Error: {error_context.exception_type}",
                severity="SEV-2",
                customer_impacted=True,
            )

            logger.info(
                "Incident created for error",
                error_id=error_id,
                occurrences=summary["count"],
            )

        except Exception as e:
            logger.error("Failed to create incident", error=str(e))

    def _level_to_alert_type(self, level: str) -> str:
        """Convert error level to Datadog alert type."""
        mapping = {
            "critical": "error",
            "error": "error",
            "warning": "warning",
            "info": "info",
        }
        return mapping.get(level, "info")

    def _format_breadcrumbs(self, breadcrumbs: List[Dict[str, Any]]) -> str:
        """Format breadcrumbs for display."""
        if not breadcrumbs:
            return "No breadcrumbs"

        lines = []
        for bc in breadcrumbs:
            lines.append(
                f"- [{bc['timestamp']}] {bc['category']}: {bc['message']}"
            )
        return "\n".join(lines)


class ErrorCaptureContext:
    """Context manager for automatic error capture."""

    def __init__(self, tracker: ErrorTracker):
        self.tracker = tracker

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.tracker.capture_exception(exc_val)
        # Don't suppress the exception
        return False
