"""Tests for trace decorator behavior."""

import asyncio

import pytest

from detra.config.loader import set_config
from detra.config.schema import DetraConfig, NodeConfig, SamplingConfig
from detra.decorators.trace import set_backend, set_evaluation_engine, set_sampling_config, trace
from detra.judges.base import EvaluationResult


class RecordingEngine:
    def __init__(self):
        self.outputs = []

    async def evaluate(self, node_config, input_data, output_data, context=None):
        self.outputs.append(output_data)
        return EvaluationResult(score=1.0, flagged=False)


class FailingBackend:
    async def emit_distribution(self, name, value, tags=None):
        raise RuntimeError("backend down")

    async def emit_count(self, name, value, tags=None):
        raise RuntimeError("backend down")

    async def emit_gauge(self, name, value, tags=None):
        raise RuntimeError("backend down")

    async def emit_event(self, title, text, level="info", tags=None):
        raise RuntimeError("backend down")

    async def flush(self):
        return None

    async def close(self):
        return None


def setup_module():
    set_sampling_config(SamplingConfig(rate=1.0))


@pytest.mark.asyncio
async def test_capture_output_false_hides_output_from_evaluation():
    set_config(DetraConfig(app_name="test", nodes={"n": NodeConfig()}))
    engine = RecordingEngine()
    set_evaluation_engine(engine)
    set_backend(FailingBackend())

    @trace("n", capture_output=False)
    async def fn():
        return "secret"

    assert await fn() == "secret"
    assert engine.outputs == [None]


@pytest.mark.asyncio
async def test_telemetry_failure_does_not_fail_wrapped_function():
    set_config(DetraConfig(app_name="test", nodes={"n": NodeConfig()}))
    set_evaluation_engine(None)
    set_backend(FailingBackend())

    @trace("n")
    async def fn():
        return "ok"

    assert await fn() == "ok"


@pytest.mark.asyncio
async def test_extractor_failure_does_not_fail_wrapped_function():
    set_config(DetraConfig(app_name="test", nodes={"n": NodeConfig()}))
    engine = RecordingEngine()
    set_evaluation_engine(engine)
    set_backend(FailingBackend())

    def bad_input(args, kwargs):
        raise RuntimeError("input extractor failed")

    def bad_output(output):
        raise RuntimeError("output extractor failed")

    @trace("n", input_extractor=bad_input, output_extractor=bad_output)
    async def fn():
        return "ok"

    assert await fn() == "ok"
    assert engine.outputs == [None]


@pytest.mark.asyncio
async def test_sync_function_in_running_loop_still_runs_guardrails():
    set_config(DetraConfig(app_name="test", nodes={"n": NodeConfig()}))
    engine = RecordingEngine()
    set_evaluation_engine(engine)
    set_backend(FailingBackend())

    @trace("n")
    def fn():
        return "sync-output"

    assert fn() == "sync-output"
    await asyncio.sleep(0)
    assert engine.outputs == ["sync-output"]
