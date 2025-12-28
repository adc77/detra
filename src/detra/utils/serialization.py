"""Serialization utilities for JSON and YAML handling."""

import json
import re
from datetime import datetime
from typing import Any, Optional


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.

    Args:
        text: String to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to add when truncating.

    Returns:
        Truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """
    Safely serialize an object to JSON string.

    Handles non-serializable types by converting them to strings.

    Args:
        obj: Object to serialize.
        **kwargs: Additional arguments passed to json.dumps.

    Returns:
        JSON string representation.
    """

    def default_serializer(o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        # Try to get string representation for custom objects
        if hasattr(o, "__str__") and type(o).__str__ is not object.__str__:
            # Use __str__ if it's been overridden (not the default object.__str__)
            return str(o)
        if hasattr(o, "__repr__") and type(o).__repr__ is not object.__repr__:
            # Use __repr__ if it's been overridden
            return repr(o)
        if hasattr(o, "__dict__"):
            # Try to serialize as dict
            try:
                return {k: default_serializer(v) for k, v in o.__dict__.items()}
            except (TypeError, ValueError):
                return str(o)
        return str(o)

    kwargs.setdefault("default", default_serializer)
    kwargs.setdefault("ensure_ascii", False)

    try:
        return json.dumps(obj, **kwargs)
    except (TypeError, ValueError) as e:
        return json.dumps({"error": f"Serialization failed: {str(e)}", "type": str(type(obj))})


def safe_json_loads(text: str, default: Optional[Any] = None) -> Optional[Any]:
    """
    Safely parse a JSON string.

    Args:
        text: JSON string to parse.
        default: Default value to return if parsing fails.

    Returns:
        Parsed JSON (dict, list, or primitive) or default value if parsing fails.
    """
    if not text or not text.strip():
        return default

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_json_from_text(text: str) -> Optional[Any]:
    """
    Extract JSON object or array from text that may contain markdown or other content.

    Handles common cases like:
    - Raw JSON (objects or arrays)
    - JSON wrapped in markdown code blocks
    - JSON embedded in other text

    Args:
        text: Text potentially containing JSON.

    Returns:
        Parsed JSON (dict, list, or primitive) or None if no valid JSON found.
    """
    text = text.strip()

    # Try direct parse first
    result = safe_json_loads(text)
    if result is not None:
        return result

    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try again after removing markdown
    result = safe_json_loads(text)
    if result is not None:
        return result

    # Try to find JSON array first (simpler pattern)
    bracket_start = text.find("[")
    if bracket_start != -1:
        bracket_count = 0
        for i, char in enumerate(text[bracket_start:], bracket_start):
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    candidate = text[bracket_start : i + 1]
                    result = safe_json_loads(candidate)
                    if result is not None:
                        return result
                    break

    # Try to find JSON object in text
    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    matches = re.findall(json_pattern, text, re.DOTALL)

    for match in matches:
        result = safe_json_loads(match)
        if result is not None:
            return result

    # Try to find nested JSON object with a more permissive pattern
    brace_start = text.find("{")
    if brace_start != -1:
        brace_count = 0
        for i, char in enumerate(text[brace_start:], brace_start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    candidate = text[brace_start : i + 1]
                    result = safe_json_loads(candidate)
                    if result is not None:
                        return result
                    break

    return None


def format_for_logging(obj: Any, max_length: int = 500) -> str:
    """
    Format an object for logging, truncating if necessary.

    Args:
        obj: Object to format.
        max_length: Maximum length of output.

    Returns:
        Formatted string suitable for logging.
    """
    if isinstance(obj, str):
        return truncate_string(obj, max_length)

    json_str = safe_json_dumps(obj, indent=None)
    return truncate_string(json_str, max_length)


def serialize_for_logging(
    obj: Any,
    max_string_length: int = 1000,
    max_depth: int = 10,
) -> Any:
    """
    Serialize an object for logging, preserving structure but truncating long strings.

    Args:
        obj: Object to serialize (dict, list, or other).
        max_string_length: Maximum length for string values.
        max_depth: Maximum depth for nested structures (prevents infinite recursion).

    Returns:
        Serialized object with same structure, but with truncated strings.
    """
    if max_depth <= 0:
        return "<max depth reached>"

    if isinstance(obj, str):
        return truncate_string(obj, max_string_length)

    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            # Handle circular references by checking if we've seen this object
            if value is obj:
                result[str(key)] = "<circular reference>"
            else:
                result[str(key)] = serialize_for_logging(
                    value, max_string_length, max_depth - 1
                )
        return result

    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            # Handle circular references
            if item is obj:
                result.append("<circular reference>")
            else:
                result.append(
                    serialize_for_logging(item, max_string_length, max_depth - 1)
                )
        return result if isinstance(obj, list) else tuple(result)

    # For other types, try to convert to string representation
    try:
        # Try to serialize as JSON first
        json_str = safe_json_dumps(obj)
        parsed = json.loads(json_str)
        
        # If it's a dict with error key, it means serialization partially failed
        # Try to preserve the string representation
        if isinstance(parsed, dict) and "error" in parsed:
            # Try __repr__ or __str__ instead
            if hasattr(obj, "__repr__"):
                str_repr = repr(obj)
            else:
                str_repr = str(obj)
            return truncate_string(str_repr, max_string_length)
        
        # Recursively process nested structures
        if isinstance(parsed, dict):
            return {k: serialize_for_logging(v, max_string_length, max_depth - 1) for k, v in parsed.items()}
        elif isinstance(parsed, list):
            return [serialize_for_logging(item, max_string_length, max_depth - 1) for item in parsed]
        
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        # Fall back to string representation
        if hasattr(obj, "__repr__"):
            str_repr = repr(obj)
        else:
            str_repr = str(obj)
        return truncate_string(str_repr, max_string_length)
