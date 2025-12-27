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
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )


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
        config.base_delay * (config.exponential_base ** attempt),
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

    for attempt in range(config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    "Retry attempt failed",
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All retry attempts exhausted",
                    attempts=config.max_attempts,
                    error=str(e),
                )

    raise RetryError(
        f"Failed after {config.max_attempts} attempts",
        last_exception=last_exception,
    )


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
