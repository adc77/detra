"""Error grouping and deduplication logic."""

import hashlib
from typing import Dict, List, Any
import re

from detra.errors.context import ErrorContext


class ErrorGrouper:
    """
    Groups similar errors together (like Sentry's error grouping).

    Uses a combination of:
    - Exception type
    - Exception message (normalized)
    - Stack trace similarity
    - Error location (file:line:function)

    This allows tracking "new" vs "recurring" errors.
    """

    def __init__(self):
        """Initialize error grouper."""
        self._groups: Dict[str, List[str]] = {}

    def get_error_id(self, error_context: ErrorContext) -> str:
        """
        Generate a unique ID for grouping similar errors.

        Args:
            error_context: The error context.

        Returns:
            12-character hex string identifying this error group.
        """
        fingerprint = self._build_fingerprint(error_context)
        fingerprint_str = "|".join(fingerprint)

        # Create hash
        error_hash = hashlib.md5(fingerprint_str.encode()).hexdigest()
        error_id = error_hash[:12]

        # Track in group
        if error_id not in self._groups:
            self._groups[error_id] = []
        self._groups[error_id].append(fingerprint_str)

        return error_id

    def _build_fingerprint(self, error_context: ErrorContext) -> List[str]:
        """
        Build fingerprint for grouping.

        Args:
            error_context: Error context.

        Returns:
            List of strings forming the fingerprint.
        """
        fingerprint = []

        # 1. Exception type
        fingerprint.append(error_context.exception_type)

        # 2. Normalized message (remove dynamic parts)
        normalized_msg = self._normalize_message(error_context.exception_message)
        fingerprint.append(normalized_msg)

        # 3. Error location (culprit)
        if error_context.traceback_frames:
            last_frame = error_context.traceback_frames[-1]
            fingerprint.append(
                f"{last_frame['filename']}:{last_frame['function']}"
            )

        # 4. Stack trace signature (hash of function names)
        if error_context.traceback_frames:
            stack_signature = self._get_stack_signature(
                error_context.traceback_frames
            )
            fingerprint.append(stack_signature)

        return fingerprint

    def _normalize_message(self, message: str) -> str:
        """
        Normalize error message by removing dynamic values.

        Examples:
            "File not found: /tmp/abc123" -> "File not found: /tmp/*"
            "Timeout after 5.3 seconds" -> "Timeout after * seconds"
        """

        # Replace file paths
        message = re.sub(r'/[^\s]+', '/path/*', message)

        # Replace numbers
        message = re.sub(r'\b\d+\.?\d*\b', '*', message)

        # Replace UUIDs
        message = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '*',
            message
        )

        # Replace hex values
        message = re.sub(r'0x[0-9a-f]+', '0x*', message)

        return message[:200]  # Limit length

    def _get_stack_signature(
        self,
        frames: List[Dict[str, Any]]
    ) -> str:
        """
        Get a signature from the stack trace.

        Args:
            frames: Traceback frames.

        Returns:
            Hash of function call sequence.
        """
        # Get function names from frames
        function_names = [f['function'] for f in frames[-5:]]  # Last 5 frames
        signature = "->".join(function_names)

        # Hash it
        return hashlib.md5(signature.encode()).hexdigest()[:8]

    def get_group_count(self, error_id: str) -> int:
        """
        Get count of errors in a group.

        Args:
            error_id: Error ID.

        Returns:
            Number of occurrences.
        """
        return len(self._groups.get(error_id, []))

    def get_all_groups(self) -> Dict[str, int]:
        """
        Get all error groups with counts.

        Returns:
            Dictionary mapping error_id to occurrence count.
        """
        return {
            error_id: len(occurrences)
            for error_id, occurrences in self._groups.items()
        }
