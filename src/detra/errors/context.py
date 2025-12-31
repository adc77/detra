"""Error context data structures."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErrorContext:
    """
    Complete context for an error occurrence.

    Similar to Sentry's error context, includes:
    - Exception details
    - Stack trace
    - Breadcrumbs (events leading to error)
    - User context
    - Environment info
    - Custom tags and data
    """

    exception_type: str
    exception_message: str
    stack_trace: str = ""
    traceback_frames: List[Dict[str, Any]] = field(default_factory=list)
    breadcrumbs: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    user_info: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    environment: str = "production"
    release: Optional[str] = None
    timestamp: str = ""
    server_name: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "stack_trace": self.stack_trace,
            "traceback_frames": self.traceback_frames,
            "breadcrumbs": self.breadcrumbs,
            "context": self.context,
            "user_info": self.user_info,
            "extra": self.extra,
            "environment": self.environment,
            "release": self.release,
            "timestamp": self.timestamp,
            "server_name": self.server_name,
            "tags": self.tags,
        }

    def get_culprit(self) -> str:
        """
        Get the culprit (function/file where error occurred).

        Returns:
            String in format "module.function" or "file:line".
        """
        if not self.traceback_frames:
            return "unknown"

        # Get the last frame (where error occurred)
        last_frame = self.traceback_frames[-1]
        return f"{last_frame['filename']}:{last_frame['line']} in {last_frame['function']}"

    def get_fingerprint(self) -> List[str]:
        """
        Get error fingerprint for grouping.

        Returns:
            List of strings that uniquely identify this error type.
        """
        fingerprint = [
            self.exception_type,
            self.exception_message[:100],  # First 100 chars
        ]

        # Add culprit location
        if self.traceback_frames:
            last_frame = self.traceback_frames[-1]
            fingerprint.append(f"{last_frame['filename']}:{last_frame['function']}")

        return fingerprint
