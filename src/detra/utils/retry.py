"""Async retry utilities with exponential backoff."""

import asyncio
import functools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.
    
    Supports both naming conventions for backward compatibility:
    - max_retries/initial_delay (primary, used by tests)
    - max_attempts/base_delay (aliases, used internally)
    """

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )

    def __post_init__(self):
        """Initialize - ensure backward compatibility with old field names."""
        # This allows both max_retries and max_attempts to work
        pass

    @property
    def max_attempts(self) -> int:
        """Alias for max_retries (for backward compatibility)."""
        return self.max_retries

    @property
    def base_delay(self) -> float:
        """Alias for initial_delay (for backward compatibility)."""
        return self.initial_delay


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for a given attempt using exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed).
        config: Retry configuration.

    Returns:
        Delay in seconds.
    """
    delay = min(
        config.initial_delay * (config.exponential_base ** attempt),
        config.max_delay,
    )
    if config.jitter:
        delay = delay * (0.5 + random.random())
    return delay


async def async_retry(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        config: Retry configuration (uses defaults if not provided).
        **kwargs: Keyword arguments for the function.

    Returns:
        Result of the function call.

    Raises:
        RetryError: If all retry attempts fail.
    """
    if config is None:
        config = RetryConfig()

    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_retries - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    "Retry attempt failed",
                    attempt=attempt + 1,
                    max_attempts=config.max_retries,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All retry attempts exhausted",
                    attempts=config.max_retries,
                    error=str(e),
                )

    error_msg = f"Retry failed after {config.max_retries} attempts"
    if last_exception:
        error_msg += f": {str(last_exception)}"
    raise RetryError(error_msg, last_exception=last_exception)


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to an async function.

    Args:
        config: Retry configuration.

    Returns:
        Decorated function with retry logic.
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await async_retry(func, *args, config=config, **kwargs)

        return wrapper

    return decorator
