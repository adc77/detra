"""Telemetry and observability components for detra.

These modules require the ``detra[datadog]`` extra.  Importing this
package without ddtrace installed will still succeed -- individual
classes are imported lazily.
"""


def __getattr__(name: str):
    _LAZY_IMPORTS = {
        "DatadogClient": "detra.telemetry.datadog_client",
        "LLMObsBridge": "detra.telemetry.llmobs_bridge",
        "MetricsSubmitter": "detra.telemetry.metrics",
        "EventSubmitter": "detra.telemetry.events",
        "StructuredLogger": "detra.telemetry.logs",
    }
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module 'detra.telemetry' has no attribute {name!r}")


__all__ = [
    "DatadogClient",
    "LLMObsBridge",
    "MetricsSubmitter",
    "EventSubmitter",
    "StructuredLogger",
]
