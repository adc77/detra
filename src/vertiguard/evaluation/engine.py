"""Main evaluation orchestrator."""

import time
from typing import Any, Optional

import structlog

from vertiguard.config.schema import NodeConfig, SecurityConfig
from vertiguard.evaluation.classifiers import FailureClassifier
from vertiguard.evaluation.gemini_judge import EvaluationResult, GeminiJudge
from vertiguard.evaluation.rules import RuleBasedChecker

logger = structlog.get_logger()


class EvaluationEngine:
    """
    Orchestrates rule-based and LLM-based evaluation.

    Runs evaluations in an efficient pipeline:
    1. Fast rule-based checks (can short-circuit)
    2. Security scans
    3. LLM-based semantic evaluation
    """

    def __init__(
        self,
        gemini_judge: GeminiJudge,
        security_config: SecurityConfig,
    ):
        """
        Initialize the evaluation engine.

        Args:
            gemini_judge: Gemini-based evaluator.
            security_config: Security configuration.
        """
        self.gemini_judge = gemini_judge
        self.security_config = security_config
        self.rule_checker = RuleBasedChecker()
        self.failure_classifier = FailureClassifier()

    async def evaluate(
        self,
        node_config: NodeConfig,
        input_data: Any,
        output_data: Any,
        context: Optional[dict[str, Any]] = None,
        skip_rules: bool = False,
        skip_security: bool = False,
        skip_llm: bool = False,
    ) -> EvaluationResult:
        """
        Full evaluation pipeline.

        Args:
            node_config: Configuration for the node being evaluated.
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            context: Additional context for evaluation.
            skip_rules: Skip rule-based checks.
            skip_security: Skip security checks.
            skip_llm: Skip LLM evaluation.

        Returns:
            EvaluationResult with all evaluation details.
        """
        start_time = time.time()

        # Phase 1: Rule-based checks (fast)
        rule_results = None
        if not skip_rules:
            rule_results = self.rule_checker.check(input_data, output_data, node_config)

            # Short-circuit if critical rule failure
            if rule_results.critical_failure:
                logger.info(
                    "Critical rule failure, skipping LLM evaluation",
                    node=node_config.description,
                    reason=rule_results.failure_reason,
                )
                return EvaluationResult(
                    score=rule_results.score,
                    flagged=True,
                    flag_reason=rule_results.failure_reason,
                    flag_category=rule_results.failure_category,
                    checks_failed=[
                        self._rule_check_to_behavior_check(c)
                        for c in rule_results.failed_checks
                    ],
                    latency_ms=(time.time() - start_time) * 1000,
                )

        # Phase 2: Security checks
        security_issues = []
        if not skip_security and node_config.security_checks:
            security_issues = await self.gemini_judge.check_security(
                input_data, output_data, node_config.security_checks
            )

        # Phase 3: LLM-based evaluation
        if skip_llm or (
            not node_config.expected_behaviors and not node_config.unexpected_behaviors
        ):
            # No behaviors to check, return based on rules and security
            score = rule_results.score if rule_results else 1.0
            flagged = bool(security_issues) or (rule_results and rule_results.failed_checks)

            return EvaluationResult(
                score=score,
                flagged=flagged,
                flag_reason="Security issue detected" if security_issues else None,
                flag_category="security_violation" if security_issues else None,
                security_issues=security_issues,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Run full LLM evaluation
        eval_result = await self.gemini_judge.evaluate(
            input_data=input_data,
            output_data=output_data,
            expected_behaviors=node_config.expected_behaviors,
            unexpected_behaviors=node_config.unexpected_behaviors,
            context=context,
        )

        # Merge security issues
        eval_result.security_issues = security_issues

        # Check against threshold
        if eval_result.score < node_config.adherence_threshold:
            eval_result.flagged = True

        # Add critical security issues to flagged
        critical_security = [
            i for i in security_issues if i.get("severity") == "critical"
        ]
        if critical_security and not eval_result.flagged:
            eval_result.flagged = True
            eval_result.flag_reason = f"Security issue: {critical_security[0].get('check')}"
            eval_result.flag_category = "security_violation"

        # Merge rule check failures if any
        if rule_results and rule_results.failed_checks:
            rule_behavior_checks = [
                self._rule_check_to_behavior_check(c)
                for c in rule_results.failed_checks
            ]
            eval_result.checks_failed.extend(rule_behavior_checks)

        # Update latency to include all phases
        eval_result.latency_ms = (time.time() - start_time) * 1000

        return eval_result

    def _rule_check_to_behavior_check(self, rule_check):
        """Convert a rule check result to behavior check format."""
        from vertiguard.evaluation.gemini_judge import BehaviorCheckResult

        return BehaviorCheckResult(
            behavior=f"RULE: {rule_check.check_name}",
            passed=rule_check.passed,
            confidence=1.0,  # Rule checks are deterministic
            reasoning=rule_check.message or "",
        )

    async def evaluate_with_retry(
        self,
        node_config: NodeConfig,
        input_data: Any,
        output_data: Any,
        context: Optional[dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> EvaluationResult:
        """
        Evaluate with retry on transient failures.

        Args:
            node_config: Configuration for the node being evaluated.
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            context: Additional context.
            max_retries: Maximum retry attempts.

        Returns:
            EvaluationResult with all evaluation details.
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await self.evaluate(
                    node_config=node_config,
                    input_data=input_data,
                    output_data=output_data,
                    context=context,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Evaluation attempt failed",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )

                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(1.0 * (attempt + 1))

        # All retries failed
        logger.error("All evaluation attempts failed", error=str(last_error))
        return EvaluationResult(
            score=0.5,
            flagged=True,
            flag_reason=f"Evaluation failed after {max_retries + 1} attempts: {str(last_error)}",
            flag_category="error",
        )

    async def quick_check(
        self,
        output_data: Any,
        node_config: Optional[NodeConfig] = None,
    ) -> dict[str, Any]:
        """
        Quick rule-based check without LLM evaluation.

        Useful for fast validation before full evaluation.

        Args:
            output_data: Output to check.
            node_config: Optional node configuration.

        Returns:
            Quick check result with pass/fail and score.
        """
        rule_results = self.rule_checker.check(None, output_data, node_config)

        return {
            "passed": not rule_results.critical_failure and not rule_results.failed_checks,
            "score": rule_results.score,
            "critical_failure": rule_results.critical_failure,
            "failure_reason": rule_results.failure_reason,
            "checks_failed": len(rule_results.failed_checks),
            "checks_passed": len(rule_results.passed_checks),
        }
