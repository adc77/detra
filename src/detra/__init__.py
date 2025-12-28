"""
detra: End-to-end LLM Observability for Vertical AI Applications

A comprehensive framework for monitoring, evaluating, and securing
LLM applications with Datadog integration.

Usage:
    import detra

    # Initialize with config file
    vg = detra.init("detra.yaml")

    # Use decorators to trace functions
    @vg.trace("extract_entities")
    def extract_entities(document):
        return llm.complete(prompt)

    # Or use module-level decorators after init
    @detra.trace("summarize")
    async def summarize(text):
        return await llm.complete(prompt)
"""

from detra.client import detra, init, get_client, is_initialized
from detra.decorators.trace import trace, workflow, llm, task, agent
from detra.config.schema import detraConfig, NodeConfig
from detra.evaluation.gemini_judge import EvaluationResult, BehaviorCheckResult

__version__ = "0.1.0"

__all__ = [
    # Client
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
    "detraConfig",
    "NodeConfig",
    # Results
    "EvaluationResult",
    "BehaviorCheckResult",
    # Version
    "__version__",
]
