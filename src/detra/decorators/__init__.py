"""Trace decorators for detra."""

from detra.decorators.trace import (
    DetraTrace,
    trace,
    workflow,
    llm,
    task,
    agent,
    set_evaluation_engine,
    set_backend,
    set_sampling_config,
)

# Backward compat
detraTrace = DetraTrace

__all__ = [
    "DetraTrace",
    "detraTrace",
    "trace",
    "workflow",
    "llm",
    "task",
    "agent",
    "set_evaluation_engine",
    "set_backend",
    "set_sampling_config",
]
