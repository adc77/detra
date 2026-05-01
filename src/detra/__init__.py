"""detra: LLM Guardrails & Observability Framework

Usage::

    import detra

    vg = detra.init("detra.yaml")

    @vg.trace("extract_entities")
    async def extract_entities(document):
        return await model.complete(prompt)
"""

from detra.backends.base import TelemetryBackend
from detra.client import Detra, detra, get_client, init, is_initialized
from detra.config.schema import DetraConfig, NodeConfig, detraConfig
from detra.decorators.trace import agent, llm, task, trace, workflow
from detra.judges.base import BehaviorCheckResult, EvaluationResult, Judge

__version__ = "0.2.0"

_LEGACY_EXPORTS = {
    "CaseManager": "detra.actions.cases",
    "DSpyOptimizer": "detra.optimization.dspy_optimizer",
    "RootCauseAnalyzer": "detra.optimization.root_cause",
}


def __getattr__(name: str):
    if name in _LEGACY_EXPORTS:
        import importlib
        import warnings

        warnings.warn(
            f"detra.{name} is deprecated; import it from {_LEGACY_EXPORTS[name]} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        module = importlib.import_module(_LEGACY_EXPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module 'detra' has no attribute {name!r}")


__all__ = [
    # Client
    "Detra",
    "detra",
    "init",
    "get_client",
    "is_initialized",
    # Decorators
    "trace",
    "workflow",
    "llm",
    "task",
    "agent",
    # Config
    "DetraConfig",
    "detraConfig",
    "NodeConfig",
    # Protocols / results
    "EvaluationResult",
    "BehaviorCheckResult",
    "Judge",
    "TelemetryBackend",
    # Legacy exports
    "CaseManager",
    "DSpyOptimizer",
    "RootCauseAnalyzer",
    # Version
    "__version__",
]
