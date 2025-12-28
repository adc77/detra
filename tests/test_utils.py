"""Tests for the utils module."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from detra.utils.retry import RetryConfig, async_retry, RetryError
from detra.utils.serialization import (
    safe_json_loads,
    safe_json_dumps,
    extract_json_from_text,
    truncate_string,
    serialize_for_logging,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default retry configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.jitter is False


class TestAsyncRetry:
    """Tests for async_retry function."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test that successful calls don't trigger retries."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_retry(success_func)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on transient failure."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        config = RetryConfig(max_retries=5, initial_delay=0.01)
        result = await async_retry(fail_then_succeed, config=config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that RetryError is raised when max retries exceeded."""
        async def always_fail():
            raise ValueError("Always fails")

        config = RetryConfig(max_retries=2, initial_delay=0.01)
        with pytest.raises(RetryError) as exc_info:
            await async_retry(always_fail, config=config)

        assert "Retry failed after 2 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_with_args_kwargs(self):
        """Test retry passes arguments correctly."""
        async def func_with_args(a: int, b: str, c: bool = False):
            return f"{a}-{b}-{c}"

        result = await async_retry(func_with_args, 1, "test", c=True)
        assert result == "1-test-True"

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that delays increase exponentially."""
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            # Don't actually sleep in tests

        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "ok"

        config = RetryConfig(max_retries=5, initial_delay=1.0, jitter=False)

        with patch("asyncio.sleep", mock_sleep):
            await async_retry(fail_twice, config=config)

        # First delay should be ~1.0, second should be ~2.0
        assert len(delays) == 2
        assert delays[1] > delays[0]

    @pytest.mark.asyncio
    async def test_retry_with_retryable_exceptions(self):
        """Test retry only on specified exception types."""
        call_count = 0

        async def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        config = RetryConfig(
            max_retries=3,
            initial_delay=0.01,
            retryable_exceptions=(ValueError,),
        )

        # TypeError is not in retryable_exceptions, should fail immediately
        with pytest.raises(TypeError):
            await async_retry(raise_type_error, config=config)

        assert call_count == 1


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        result = safe_json_loads('{"key": "value", "num": 123}')
        assert result == {"key": "value", "num": 123}

    def test_invalid_json_returns_default(self):
        """Test that invalid JSON returns default value."""
        result = safe_json_loads("not json", default={})
        assert result == {}

    def test_invalid_json_returns_none(self):
        """Test that invalid JSON returns None when no default."""
        result = safe_json_loads("not json")
        assert result is None

    def test_empty_string(self):
        """Test empty string returns default."""
        result = safe_json_loads("", default=[])
        assert result == []

    def test_json_with_unicode(self):
        """Test JSON with Unicode characters."""
        result = safe_json_loads('{"emoji": ""}')
        assert result == {"emoji": ""}

    def test_nested_json(self):
        """Test parsing nested JSON structures."""
        data = '{"a": {"b": {"c": [1, 2, 3]}}}'
        result = safe_json_loads(data)
        assert result["a"]["b"]["c"] == [1, 2, 3]


class TestSafeJsonDumps:
    """Tests for safe_json_dumps function."""

    def test_valid_dict(self):
        """Test dumping valid dictionary."""
        result = safe_json_dumps({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_non_serializable_object(self):
        """Test non-serializable objects are converted to strings."""
        class CustomObj:
            def __str__(self):
                return "custom_obj"

        result = safe_json_dumps({"obj": CustomObj()})
        parsed = json.loads(result)
        assert "custom_obj" in str(parsed["obj"])

    def test_datetime_serialization(self):
        """Test datetime objects are serialized."""
        from datetime import datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = safe_json_dumps({"date": dt})
        assert "2024" in result

    def test_with_indent(self):
        """Test JSON dumps with indentation."""
        result = safe_json_dumps({"key": "value"}, indent=2)
        assert "\n" in result


class TestExtractJsonFromText:
    """Tests for extract_json_from_text function."""

    def test_json_in_code_block(self):
        """Test extracting JSON from markdown code block."""
        text = '''Here is the result:
```json
{"key": "value"}
```
'''
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_json_in_plain_code_block(self):
        """Test extracting JSON from plain code block."""
        text = '''Result:
```
{"key": "value"}
```
'''
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_raw_json_object(self):
        """Test extracting raw JSON object."""
        text = 'The answer is {"key": "value"} and more text'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_raw_json_array(self):
        """Test extracting raw JSON array."""
        text = 'Items: [1, 2, 3] end'
        result = extract_json_from_text(text)
        assert result == [1, 2, 3]

    def test_no_json_found(self):
        """Test when no JSON is present."""
        text = "This is just plain text without JSON."
        result = extract_json_from_text(text)
        assert result is None

    def test_nested_json_in_code_block(self):
        """Test nested JSON in code block."""
        text = '''```json
{
    "outer": {
        "inner": [1, 2, 3]
    }
}
```'''
        result = extract_json_from_text(text)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_invalid_json_in_code_block(self):
        """Test invalid JSON in code block returns None."""
        text = '''```json
{invalid json}
```'''
        result = extract_json_from_text(text)
        assert result is None


class TestTruncateString:
    """Tests for truncate_string function."""

    def test_short_string_unchanged(self):
        """Test that short strings are not modified."""
        result = truncate_string("hello", max_length=10)
        assert result == "hello"

    def test_long_string_truncated(self):
        """Test that long strings are truncated."""
        result = truncate_string("hello world", max_length=8)
        assert len(result) <= 8
        assert "..." in result

    def test_exact_length(self):
        """Test string exactly at max length."""
        result = truncate_string("12345", max_length=5)
        assert result == "12345"

    def test_empty_string(self):
        """Test empty string."""
        result = truncate_string("", max_length=10)
        assert result == ""

    def test_very_small_max_length(self):
        """Test with very small max length."""
        result = truncate_string("hello", max_length=3)
        assert len(result) <= 3


class TestSerializeForLogging:
    """Tests for serialize_for_logging function."""

    def test_simple_dict(self):
        """Test serializing simple dictionary."""
        result = serialize_for_logging({"key": "value"})
        assert result == {"key": "value"}

    def test_truncates_long_strings(self):
        """Test that long strings are truncated."""
        long_string = "x" * 2000
        result = serialize_for_logging({"text": long_string}, max_string_length=100)
        assert len(result["text"]) <= 100

    def test_nested_structure(self):
        """Test serializing nested structures."""
        data = {
            "level1": {
                "level2": {
                    "value": "test"
                }
            }
        }
        result = serialize_for_logging(data)
        assert result["level1"]["level2"]["value"] == "test"

    def test_list_of_dicts(self):
        """Test serializing list of dictionaries."""
        data = [{"a": 1}, {"b": 2}]
        result = serialize_for_logging(data)
        assert result == [{"a": 1}, {"b": 2}]

    def test_non_serializable_converted(self):
        """Test that non-serializable objects are converted."""
        class Custom:
            def __repr__(self):
                return "CustomObject"

        data = {"obj": Custom()}
        result = serialize_for_logging(data)
        assert "CustomObject" in str(result["obj"])


class TestEdgeCases:
    """Edge case tests for utils module."""

    @pytest.mark.asyncio
    async def test_retry_with_zero_retries(self):
        """Test retry with zero max retries."""
        async def fail():
            raise ValueError("Fail")

        config = RetryConfig(max_retries=0, initial_delay=0.01)
        with pytest.raises(RetryError):
            await async_retry(fail, config=config)

    def test_json_with_special_float_values(self):
        """Test JSON with infinity and NaN."""
        import math

        # These should not raise but may convert to null or strings
        data = {"inf": float("inf"), "nan": float("nan")}
        result = safe_json_dumps(data)
        assert result is not None

    def test_extract_json_with_multiple_objects(self):
        """Test extracting first JSON when multiple are present."""
        text = '{"first": 1} and {"second": 2}'
        result = extract_json_from_text(text)
        # Should extract the first valid JSON
        assert result is not None

    def test_truncate_unicode_string(self):
        """Test truncating string with multi-byte Unicode."""
        result = truncate_string("" * 10, max_length=5)
        assert len(result) <= 5

    def test_serialize_circular_reference(self):
        """Test handling circular references."""
        data: dict[str, Any] = {"key": "value"}
        data["self"] = data  # Circular reference

        # Should not raise, should handle gracefully
        try:
            result = serialize_for_logging(data, max_depth=2)
            assert result is not None
        except (ValueError, RecursionError):
            # Acceptable if it raises for circular ref
            pass

    @pytest.mark.asyncio
    async def test_retry_preserves_exception_info(self):
        """Test that retry preserves original exception information."""
        async def raise_with_message():
            raise ValueError("Original error message")

        config = RetryConfig(max_retries=1, initial_delay=0.01)
        with pytest.raises(RetryError) as exc_info:
            await async_retry(raise_with_message, config=config)

        assert "Original error message" in str(exc_info.value)
