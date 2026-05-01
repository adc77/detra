"""Tests for client resolution behavior."""

from detra.client import _resolve_judge
from detra.config.schema import DetraConfig, JudgeConfig, JudgeProvider


def test_explicit_gemini_judge_works_without_legacy_gemini_section():
    config = DetraConfig(
        app_name="test",
        judge_config=JudgeConfig(
            provider=JudgeProvider.GEMINI,
            api_key="test-key",
            model="gemini-2.5-flash",
        ),
        gemini=None,
    )

    judge = _resolve_judge(config)

    assert judge is not None
    assert config.gemini is not None
    assert config.gemini.api_key == "test-key"
