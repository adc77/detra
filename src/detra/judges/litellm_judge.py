"""LiteLLM-based judge -- evaluates with any LLM provider.

Supports 100+ providers through litellm: OpenAI, Anthropic, Google,
Azure, Cohere, Mistral, Ollama, HuggingFace, and more.

Requires: pip install detra[litellm]
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from detra.evaluation.prompts import BATCH_BEHAVIOR_CHECK_PROMPT, SECURITY_CHECK_PROMPT
from detra.judges.base import BehaviorCheckResult, EvaluationResult
from detra.utils.serialization import extract_json_from_text, safe_json_dumps, truncate_string

logger = structlog.get_logger()

try:
    import litellm

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False


class LiteLLMJudge:
    """Judge backed by any LLM reachable through litellm.

    Pass *any* model string litellm understands (``gpt-4o-mini``,
    ``claude-sonnet-4-20250514``, ``gemini/gemini-2.5-flash``, ``ollama/llama3``, ...).
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        if not _LITELLM_AVAILABLE:
            raise ImportError(
                "litellm required for LiteLLMJudge.  Install with: pip install detra[litellm]"
            )
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    # -- Judge protocol ----------------------------------------------------

    async def evaluate_behaviors(
        self,
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        if not expected_behaviors and not unexpected_behaviors:
            return EvaluationResult(score=1.0, flagged=False)

        start = time.time()
        input_str = truncate_string(str(input_data), 3000)
        output_str = truncate_string(str(output_data), 3000)

        prompt = BATCH_BEHAVIOR_CHECK_PROMPT.format(
            input_data=input_str,
            output_data=output_str,
            context=truncate_string(safe_json_dumps(context or {}), 2000),
            expected_behaviors="\n".join(f"- {b}" for b in expected_behaviors),
            unexpected_behaviors="\n".join(f"- {b}" for b in unexpected_behaviors),
        )

        try:
            text = await self._complete(prompt)
            data = extract_json_from_text(text)
            if not data:
                return EvaluationResult(
                    score=0.5,
                    flagged=True,
                    flag_reason="Judge returned unparseable response",
                    flag_category="error",
                    latency_ms=(time.time() - start) * 1000,
                )
            return self._parse_batch(data, expected_behaviors, unexpected_behaviors, start)
        except Exception as e:
            logger.error("litellm_judge.evaluate_behaviors failed", error=str(e))
            return EvaluationResult(
                score=0.5,
                flagged=True,
                flag_reason=f"Judge error: {e}",
                flag_category="error",
                latency_ms=(time.time() - start) * 1000,
            )

    async def check_security(
        self,
        input_data: Any,
        output_data: Any,
        checks: list[str],
    ) -> list[dict[str, Any]]:
        if not checks:
            return []

        prompt = SECURITY_CHECK_PROMPT.format(
            input_data=truncate_string(str(input_data), 2000),
            output_data=truncate_string(str(output_data), 2000),
            checks=safe_json_dumps(checks),
        )

        try:
            text = await self._complete(prompt)
            data = extract_json_from_text(text)
            if not data:
                return []
            return [i for i in data.get("issues", []) if i.get("detected")]
        except Exception as e:
            logger.error("litellm_judge.check_security failed", error=str(e))
            return []

    # -- internals ---------------------------------------------------------

    async def _complete(self, prompt: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    def _parse_batch(
        self,
        data: dict[str, Any],
        expected: list[str],
        unexpected: list[str],
        start_time: float,
    ) -> EvaluationResult:
        passed: list[BehaviorCheckResult] = []
        failed: list[BehaviorCheckResult] = []

        for i, r in enumerate(data.get("expected_results", [])):
            behavior = r.get("behavior", expected[i] if i < len(expected) else "?")
            check = BehaviorCheckResult(
                behavior=behavior,
                passed=r.get("present", False),
                confidence=r.get("confidence", 0.5),
                reasoning=r.get("reasoning", ""),
                evidence=r.get("evidence"),
            )
            (passed if check.passed else failed).append(check)

        for i, r in enumerate(data.get("unexpected_results", [])):
            behavior = r.get("behavior", unexpected[i] if i < len(unexpected) else "?")
            if r.get("detected", False):
                failed.append(BehaviorCheckResult(
                    behavior=f"UNEXPECTED: {behavior}",
                    passed=False,
                    confidence=r.get("confidence", 0.5),
                    reasoning=r.get("reasoning", ""),
                    evidence=r.get("evidence"),
                ))

        total = len(expected) + len(unexpected)
        unexpected_fails = sum(1 for c in failed if c.behavior.startswith("UNEXPECTED:"))
        passed_count = len(passed) + (len(unexpected) - unexpected_fails)
        score = passed_count / total if total > 0 else 1.0

        is_flagged = len(failed) > 0 or score < 0.5
        return EvaluationResult(
            score=score,
            flagged=is_flagged,
            flag_reason=data.get("overall_assessment") if is_flagged else None,
            flag_category="low_score" if is_flagged and not failed else None,
            checks_passed=passed,
            checks_failed=failed,
            raw_evaluation=data,
            latency_ms=(time.time() - start_time) * 1000,
        )
