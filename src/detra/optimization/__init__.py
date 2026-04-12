"""Prompt optimization and improvement modules.

These require ``detra[gemini]`` and/or ``detra[optimization]`` extras.
"""


def __getattr__(name: str):
    _LAZY = {
        "DSpyOptimizer": "detra.optimization.dspy_optimizer",
        "RootCauseAnalyzer": "detra.optimization.root_cause",
    }
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module 'detra.optimization' has no attribute {name!r}")


__all__ = ["DSpyOptimizer", "RootCauseAnalyzer"]
