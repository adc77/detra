"""detra: LLM Guardrails & Observability Framework

Usage::

    import detra

    vg = detra.init("detra.yaml")

    @vg.trace("extract_entities")
    async def extract_entities(document):
        return await model.complete(prompt)
"""

from detra.client import Detra, detra, init, get_client, is_initialized
from detra.decorators.trace import trace, workflow, llm, task, agent
from detra.config.schema import DetraConfig, detraConfig, NodeConfig
from detra.judges.base import EvaluationResult, BehaviorCheckResult, Judge
from detra.backends.base import TelemetryBackend

__version__ = "0.2.0"

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
    # Version
    "__version__",
]
