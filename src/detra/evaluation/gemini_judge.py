"""Gemini-based LLM-as-Judge evaluation engine."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import google.genai as genai
import structlog
import tiktoken

from detra.config.schema import GeminiConfig
from detra.evaluation.prompts import (
    BATCH_BEHAVIOR_CHECK_PROMPT,
    BEHAVIOR_CHECK_PROMPT,
    ROOT_CAUSE_CLASSIFICATION_PROMPT,
    SECURITY_CHECK_PROMPT,
)
from detra.utils.retry import RetryConfig, async_retry
from detra.utils.serialization import extract_json_from_text, safe_json_dumps, truncate_string

logger = structlog.get_logger()

# Initialize tiktoken encoder for token counting
# Using cl100k_base which is compatible with GPT models and provides reasonable estimates
_token_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text: Text to count tokens for.
    
    Returns:
        Number of tokens.
    """
    if not text:
        return 0
    try:
        return len(_token_encoder.encode(str(text)))
    except Exception as e:
        logger.warning("Failed to count tokens", error=str(e))
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(str(text)) // 4


@dataclass
class BehaviorCheckResult:
    """Result of a single behavior check."""
    behavior: str
    passed: bool
    reasoning: str
    confidence: float = 0.0
    evidence: Optional[str] = None


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    score: float  # 0.0 to 1.0
    flagged: bool
    flag_reason: Optional[str] = None
    flag_category: Optional[str] = None
    checks_passed: list[BehaviorCheckResult] = field(default_factory=list)
    checks_failed: list[BehaviorCheckResult] = field(default_factory=list)
    security_issues: list[dict[str, Any]] = field(default_factory=list)
    raw_evaluation: Optional[dict[str, Any]] = None
    latency_ms: float = 0.0
    eval_tokens_used: int = 0


class GeminiJudge:
    """
    Gemini-powered evaluation judge for LLM outputs.

    Uses Gemini as an LLM-as-judge to evaluate outputs against
    expected and unexpected behaviors.
    """

    def __init__(self, config: GeminiConfig):
        """
        Initialize the Gemini judge.

        Args:
            config: Gemini configuration.
        """
        self.config = config
        self._client: Optional[genai.Client] = None
        self._setup_complete = False

    def _setup_client(self) -> None:
        """Initialize Gemini client lazily."""
        if self._setup_complete:
            return

        if not self.config.api_key:
            raise ValueError("Gemini API key not found in configuration")

        self._client = genai.Client(api_key=self.config.api_key)
        self._setup_complete = True
        logger.info("Gemini client initialized", model=self.config.model.value)

    async def evaluate(
        self,
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        Comprehensive evaluation of LLM output against expected behaviors.

        Args:
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            expected_behaviors: List of behaviors that should be present.
            unexpected_behaviors: List of behaviors that should NOT be present.
            context: Additional context for evaluation.

        Returns:
            EvaluationResult with scores and details.
        """
        self._setup_client()
        start_time = time.time()

        # Use batch evaluation for efficiency
        result = await self._evaluate_batch(
            input_data=input_data,
            output_data=output_data,
            expected_behaviors=expected_behaviors,
            unexpected_behaviors=unexpected_behaviors,
            context=context,
        )

        result.latency_ms = (time.time() - start_time) * 1000
        return result

    async def _evaluate_batch(
        self,
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate all behaviors in a single LLM call."""
        if not expected_behaviors and not unexpected_behaviors:
            return EvaluationResult(score=1.0, flagged=False)

        input_str = truncate_string(str(input_data), 3000)
        output_str = truncate_string(str(output_data), 3000)
        prompt = BATCH_BEHAVIOR_CHECK_PROMPT.format(
            input=input_str,
            input_data=input_str,
            output=output_str,
            output_data=output_str,
            expected_behaviors="\n".join(f"- {b}" for b in expected_behaviors),
            unexpected_behaviors="\n".join(f"- {b}" for b in unexpected_behaviors),
        )

        try:
            response_text = await self._generate_async(prompt)
            result_data = extract_json_from_text(response_text)

            if not result_data:
                logger.warning("Failed to parse batch evaluation response")
                # Fall back to individual checks
                return await self._evaluate_individual(
                    input_data, output_data, expected_behaviors, unexpected_behaviors, context
                )

            # Count tokens used (prompt + response)
            tokens_used = count_tokens(prompt) + count_tokens(response_text)

            return self._parse_batch_result(
                result_data,
                expected_behaviors,
                unexpected_behaviors,
                tokens_used,
            )

        except Exception as e:
            logger.error("Batch evaluation failed", error=str(e))
            return EvaluationResult(
                score=0.5,
                flagged=True,
                flag_reason=f"Evaluation error: {str(e)}",
                flag_category="error",
            )

    async def _evaluate_individual(
        self,
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate behaviors individually (fallback method)."""
        checks_passed = []
        checks_failed = []
        total_tokens = 0

        # Check expected behaviors
        for behavior in expected_behaviors:
            result = await self._check_behavior(
                input_data, output_data, behavior, should_pass=True, context=context
            )
            total_tokens += result.get("tokens_used", 0)

            check_result = BehaviorCheckResult(
                behavior=behavior,
                passed=result["passed"],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                evidence=result.get("evidence"),
            )

            if result["passed"]:
                checks_passed.append(check_result)
            else:
                checks_failed.append(check_result)

        # Check unexpected behaviors
        for behavior in unexpected_behaviors:
            result = await self._check_behavior(
                input_data, output_data, behavior, should_pass=False, context=context
            )
            total_tokens += result.get("tokens_used", 0)

            detected = result["passed"]  # If behavior IS present, it's bad

            if detected:
                check_result = BehaviorCheckResult(
                    behavior=f"UNEXPECTED: {behavior}",
                    passed=False,
                    confidence=result["confidence"],
                    reasoning=result["reasoning"],
                    evidence=result.get("evidence"),
                )
                checks_failed.append(check_result)

        # Calculate score
        total_checks = len(expected_behaviors) + len(unexpected_behaviors)
        unexpected_failures = len(
            [c for c in checks_failed if c.behavior.startswith("UNEXPECTED:")]
        )
        passed_count = len(checks_passed) + (len(unexpected_behaviors) - unexpected_failures)
        score = passed_count / total_checks if total_checks > 0 else 1.0

        # Classify failures if any
        flag_reason = None
        flag_category = None
        if checks_failed:
            classification = await self._classify_failure(
                input_data, output_data, checks_failed
            )
            flag_reason = classification["reason"]
            flag_category = classification["category"]
            total_tokens += classification.get("tokens_used", 0)

        # Flag if checks failed or score is below threshold
        is_flagged = len(checks_failed) > 0 or score < 0.5
        
        return EvaluationResult(
            score=score,
            flagged=is_flagged,
            flag_reason=flag_reason if is_flagged else None,
            flag_category=flag_category if is_flagged else None,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            eval_tokens_used=total_tokens,
        )

    def _parse_batch_result(
        self,
        result_data: dict[str, Any],
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        tokens_used: int,
    ) -> EvaluationResult:
        """Parse batch evaluation result."""
        checks_passed = []
        checks_failed = []

        # Parse expected behavior results
        expected_results = result_data.get("expected_results", [])
        for i, result in enumerate(expected_results):
            behavior = result.get("behavior", expected_behaviors[i] if i < len(expected_behaviors) else "unknown")
            passed = result.get("present", False)

            check = BehaviorCheckResult(
                behavior=behavior,
                passed=passed,
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                evidence=result.get("evidence"),
            )

            if passed:
                checks_passed.append(check)
            else:
                checks_failed.append(check)

        # Parse unexpected behavior results
        unexpected_results = result_data.get("unexpected_results", [])
        for i, result in enumerate(unexpected_results):
            behavior = result.get("behavior", unexpected_behaviors[i] if i < len(unexpected_behaviors) else "unknown")
            detected = result.get("detected", False)

            if detected:
                check = BehaviorCheckResult(
                    behavior=f"UNEXPECTED: {behavior}",
                    passed=False,
                    confidence=result.get("confidence", 0.5),
                    reasoning=result.get("reasoning", ""),
                    evidence=result.get("evidence"),
                )
                checks_failed.append(check)

        # Calculate score
        total_checks = len(expected_behaviors) + len(unexpected_behaviors)
        unexpected_failures = len([c for c in checks_failed if c.behavior.startswith("UNEXPECTED:")])
        passed_count = len(checks_passed) + (len(unexpected_behaviors) - unexpected_failures)
        score = passed_count / total_checks if total_checks > 0 else 1.0

        # Flag if checks failed or score is below threshold
        is_flagged = len(checks_failed) > 0 or score < 0.5
        
        return EvaluationResult(
            score=score,
            flagged=is_flagged,
            flag_reason=result_data.get("overall_assessment") if is_flagged else None,
            flag_category="low_score" if score < 0.5 and len(checks_failed) == 0 else None,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            raw_evaluation=result_data,
            eval_tokens_used=tokens_used,
        )

    async def _check_behavior(
        self,
        input_data: Any,
        output_data: Any,
        behavior: str,
        should_pass: bool,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Check if a specific behavior is exhibited in the output."""
        input_str = truncate_string(str(input_data), 2000)
        output_str = truncate_string(str(output_data), 2000)
        prompt = BEHAVIOR_CHECK_PROMPT.format(
            input=input_str,
            input_data=input_str,
            output=output_str,
            output_data=output_str,
            behavior=behavior,
            context=safe_json_dumps(context) if context else "None",
            check_type="present" if should_pass else "absent",
        )

        try:
            response_text = await self._generate_async(prompt)
            result = extract_json_from_text(response_text)

            if not result:
                return {
                    "passed": False,
                    "confidence": 0.0,
                    "reasoning": "Failed to parse response",
                    "tokens_used": 0,
                }

            behavior_present = result.get("behavior_present", False)

            # Count tokens used
            tokens_used = count_tokens(prompt) + count_tokens(response_text)

            return {
                "passed": behavior_present if should_pass else not behavior_present,
                "confidence": result.get("confidence", 0.5),
                "reasoning": result.get("reasoning", ""),
                "evidence": result.get("evidence"),
                "tokens_used": tokens_used,
            }
        except Exception as e:
            return {
                "passed": False,
                "confidence": 0.0,
                "reasoning": f"Evaluation error: {str(e)}",
                "tokens_used": 0,
            }

    async def _classify_failure(
        self,
        input_data: Any,
        output_data: Any,
        failed_checks: list[BehaviorCheckResult],
    ) -> dict[str, Any]:
        """Classify the root cause of failures."""
        failures_text = "\n".join(
            f"- {check.behavior}: {check.reasoning}" for check in failed_checks
        )

        input_str = truncate_string(str(input_data), 1500)
        output_str = truncate_string(str(output_data), 1500)
        prompt = ROOT_CAUSE_CLASSIFICATION_PROMPT.format(
            input_data=input_str,
            output_data=output_str,
            failures=failures_text,
            behavior="",  # Placeholder for behavior analysis
            reasoning="",  # Placeholder for reasoning
        )

        try:
            response_text = await self._generate_async(prompt)
            result = extract_json_from_text(response_text)

            if not result:
                return {
                    "category": "unclassified",
                    "reason": "Failed to classify",
                    "severity": "medium",
                    "tokens_used": 0,
                }

            # Count tokens used
            tokens_used = count_tokens(prompt) + count_tokens(response_text)

            return {
                "category": result.get("category", "unclassified"),
                "reason": result.get("reason", "Unknown failure"),
                "severity": result.get("severity", "medium"),
                "remediation_hints": result.get("remediation_hints", []),
                "tokens_used": tokens_used,
            }
        except Exception as e:
            return {
                "category": "error",
                "reason": f"Classification error: {str(e)}",
                "severity": "unknown",
                "tokens_used": 0,
            }

    async def check_security(
        self,
        input_data: Any,
        output_data: Any,
        checks: list[str],
    ) -> list[dict[str, Any]]:
        """
        Run security checks on input/output.

        Args:
            input_data: Input data to check.
            output_data: Output data to check.
            checks: List of security check types.

        Returns:
            List of detected security issues.
        """
        if not checks:
            return []

        self._setup_client()

        input_str = truncate_string(str(input_data), 2000)
        output_str = truncate_string(str(output_data), 2000)
        prompt = SECURITY_CHECK_PROMPT.format(
            input_data=input_str,
            output=output_str,
            output_data=output_str,
            checks=safe_json_dumps(checks),
        )

        try:
            response_text = await self._generate_async(prompt)
            result = extract_json_from_text(response_text)

            if not result:
                return []

            issues = result.get("issues", [])
            # Filter to only detected issues
            return [i for i in issues if i.get("detected", False)]

        except Exception as e:
            logger.error("Security check failed", error=str(e))
            return []

    async def _generate_async(self, prompt: str) -> str:
        """Generate content asynchronously with retry."""
        if not self._client:
            raise RuntimeError("Gemini client not initialized")

        config = RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            retryable_exceptions=(Exception,),
        )

        async def generate():
            loop = asyncio.get_event_loop()
            # Use run_in_executor for the synchronous API call
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self.config.model.value,
                    contents=prompt,
                )
            )
            # Extract text from response
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                # Handle different response formats
                candidate = response.candidates[0]
                if hasattr(candidate, "content"):
                    if hasattr(candidate.content, "parts"):
                        parts = candidate.content.parts
                        if parts and hasattr(parts[0], "text"):
                            return parts[0].text
            # Fallback: try to get text from response
            return str(response)

        return await async_retry(generate, config=config)
