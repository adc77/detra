"""Main detra client -- pluggable backends and judges."""

from __future__ import annotations

import atexit
from typing import Any, Optional

import structlog

from detra.backends.base import TelemetryBackend
from detra.backends.console import ConsoleBackend
from detra.config.loader import load_config, set_config
from detra.config.schema import (
    BackendType,
    DetraConfig,
    JudgeProvider,
)
from detra.decorators.trace import (
    set_backend,
    set_evaluation_engine,
    set_sampling_config,
    trace as _trace,
    workflow as _workflow,
    llm as _llm,
    task as _task,
    agent as _agent,
)
from detra.evaluation.engine import EvaluationEngine
from detra.judges.base import EvaluationResult, Judge

logger = structlog.get_logger()

_client: Optional["Detra"] = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class Detra:
    """LLM guardrails and observability client.

    Usage::

        import detra

        vg = detra.init("detra.yaml")

        @vg.trace("extract_entities")
        async def extract_entities(doc: str):
            return await model.complete(prompt)

    The backend (where telemetry goes) and judge (which LLM evaluates
    outputs) are both pluggable.  Pass them explicitly or let the client
    auto-detect from the config file.
    """

    def __init__(
        self,
        config: DetraConfig,
        backend: TelemetryBackend | None = None,
        judge: Judge | None = None,
    ):
        self.config = config
        set_config(config)

        self.backend: TelemetryBackend = backend or _resolve_backend(config)
        self.judge: Judge | None = judge or _resolve_judge(config)
        self.evaluation_engine: EvaluationEngine | None = (
            EvaluationEngine(self.judge, config.security) if self.judge else None
        )

        # Wire module-level state for decorators
        set_backend(self.backend)
        set_evaluation_engine(self.evaluation_engine)
        set_sampling_config(config.sampling)

        atexit.register(self._cleanup)

        logger.info(
            "detra initialized",
            app=config.app_name,
            backend=type(self.backend).__name__,
            judge=type(self.judge).__name__ if self.judge else "none",
            sampling_rate=config.sampling.rate,
            nodes=list(config.nodes.keys()),
        )

    # -- decorators --------------------------------------------------------

    def trace(self, node_name: str, **kw):
        return _trace(node_name, **kw)

    def workflow(self, node_name: str, **kw):
        return _workflow(node_name, **kw)

    def llm(self, node_name: str, **kw):
        return _llm(node_name, **kw)

    def task(self, node_name: str, **kw):
        return _task(node_name, **kw)

    def agent(self, node_name: str, **kw):
        return _agent(node_name, **kw)

    # -- evaluation --------------------------------------------------------

    async def evaluate(
        self,
        node_name: str,
        input_data: Any,
        output_data: Any,
        context: dict | None = None,
    ) -> EvaluationResult:
        if not self.evaluation_engine:
            raise RuntimeError("No judge configured -- cannot evaluate")
        node_config = self.config.nodes.get(node_name)
        if not node_config:
            raise ValueError(f"Unknown node: {node_name}")
        return await self.evaluation_engine.evaluate(
            node_config=node_config,
            input_data=input_data,
            output_data=output_data,
            context=context,
        )

    # -- lifecycle ---------------------------------------------------------

    async def flush(self) -> None:
        await self.backend.flush()

    async def close(self) -> None:
        await self.backend.close()

    def _cleanup(self) -> None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.backend.flush())
        except RuntimeError:
            try:
                asyncio.run(self.backend.flush())
            except Exception:
                pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Backend / judge resolution
# ---------------------------------------------------------------------------

def _resolve_backend(config: DetraConfig) -> TelemetryBackend:
    """Pick a backend: explicit config > legacy DD creds > console."""

    if config.backend == BackendType.DATADOG:
        return _make_datadog(config)
    if config.backend == BackendType.OTEL:
        return _make_otel(config)
    if config.backend == BackendType.CONSOLE:
        return ConsoleBackend(config.app_name)

    # AUTO (default): sniff DD creds, fall back to console
    if (
        config.datadog
        and config.datadog.api_key
        and not config.datadog.api_key.startswith("${")
    ):
        try:
            return _make_datadog(config)
        except ImportError:
            logger.warning("Datadog keys present but ddtrace not installed -- falling back to console")

    return ConsoleBackend(config.app_name)


def _make_datadog(config: DetraConfig) -> TelemetryBackend:
    from detra.backends.datadog import DatadogBackend

    if not config.datadog:
        raise ValueError("datadog config section required for Datadog backend")
    return DatadogBackend(config.datadog)


def _make_otel(config: DetraConfig) -> TelemetryBackend:
    from detra.backends.otel import OTelBackend

    return OTelBackend(config.app_name)


def _resolve_judge(config: DetraConfig) -> Judge | None:
    """Pick a judge: explicit config > legacy Gemini creds > None."""

    jc = config.judge_config
    if jc and jc.provider == JudgeProvider.LITELLM:
        try:
            from detra.judges.litellm_judge import LiteLLMJudge

            return LiteLLMJudge(
                model=jc.model,
                api_key=jc.api_key,
                temperature=jc.temperature,
                max_tokens=jc.max_tokens,
            )
        except ImportError:
            logger.warning("litellm not installed -- falling back to legacy judge detection")
    if jc and jc.provider == JudgeProvider.GEMINI:
        try:
            return _make_gemini(config)
        except ImportError:
            logger.warning("google-genai not installed for judge_config.provider=gemini")

    # Legacy: Gemini section with a real key
    if (
        config.gemini
        and config.gemini.api_key
        and not config.gemini.api_key.startswith("${")
    ):
        try:
            return _make_gemini(config)
        except ImportError:
            logger.warning("Gemini key present but google-genai not installed")

    return None


def _make_gemini(config: DetraConfig) -> Judge:
    from detra.evaluation.gemini_judge import GeminiJudge

    if not config.gemini:
        raise ValueError("gemini config section required for Gemini judge")
    return GeminiJudge(config.gemini)


# ---------------------------------------------------------------------------
# Module-level API
# ---------------------------------------------------------------------------

def init(
    config_path: str | None = None,
    env_file: str | None = None,
    *,
    backend: TelemetryBackend | None = None,
    judge: Judge | None = None,
    **kwargs,
) -> Detra:
    global _client
    config = load_config(config_path=config_path, env_file=env_file)
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    _client = Detra(config, backend=backend, judge=judge)
    return _client


def get_client() -> Detra:
    if _client is None:
        raise RuntimeError("detra not initialized.  Call detra.init() first.")
    return _client


def is_initialized() -> bool:
    return _client is not None


# Backward compat alias
detra = Detra
