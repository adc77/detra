"""Main evaluation orchestrator."""

from __future__ import annotations

import time
from typing import Any, Optional

import structlog

from detra.config.schema import NodeConfig, SecurityConfig
from detra.evaluation.classifiers import FailureClassifier
from detra.evaluation.rules import RuleBasedChecker
from detra.judges.base import BehaviorCheckResult, EvaluationResult, Judge

logger = structlog.get_logger()


class EvaluationEngine:
    """Runs evaluations in a three-phase pipeline:

    1. Fast deterministic rule checks (can short-circuit)
    2. LLM-assisted security scans
    3. LLM-based semantic evaluation against behavior spec
    """

    def __init__(self, judge: Judge, security_config: SecurityConfig):
        self.judge = judge
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
        start_time = time.time()

        # Phase 1: rule-based checks
        rule_results = None
        if not skip_rules:
            rule_results = self.rule_checker.check(input_data, output_data, node_config)
            if rule_results.critical_failure:
                logger.info(
                    "Critical rule failure -- skipping LLM evaluation",
                    node=node_config.description,
                    reason=rule_results.failure_reason,
                )
                return EvaluationResult(
                    score=rule_results.score,
                    flagged=True,
                    flag_reason=rule_results.failure_reason,
                    flag_category=rule_results.failure_category,
                    checks_failed=[
                        self._rule_to_behavior(c) for c in rule_results.failed_checks
                    ],
                    latency_ms=(time.time() - start_time) * 1000,
                )

        # Phase 2: security
        security_issues: list[dict[str, Any]] = []
        if not skip_security and node_config.security_checks:
            security_issues = await self.judge.check_security(
                input_data, output_data, node_config.security_checks
            )

        # Phase 3: LLM evaluation
        if skip_llm or (
            not node_config.expected_behaviors and not node_config.unexpected_behaviors
        ):
            score = rule_results.score if rule_results else 1.0
            flagged = bool(security_issues) or bool(
                rule_results and rule_results.failed_checks
            )
            return EvaluationResult(
                score=score,
                flagged=flagged,
                flag_reason="Security issue detected" if security_issues else None,
                flag_category="security_violation" if security_issues else None,
                security_issues=security_issues,
                latency_ms=(time.time() - start_time) * 1000,
            )

        eval_result = await self.judge.evaluate_behaviors(
            input_data=input_data,
            output_data=output_data,
            expected_behaviors=node_config.expected_behaviors,
            unexpected_behaviors=node_config.unexpected_behaviors,
            context=context,
        )

        eval_result.security_issues = security_issues

        if eval_result.score < node_config.adherence_threshold:
            eval_result.flagged = True

        critical_security = [
            i for i in security_issues if i.get("severity") == "critical"
        ]
        if critical_security and not eval_result.flagged:
            eval_result.flagged = True
            eval_result.flag_reason = f"Security issue: {critical_security[0].get('check')}"
            eval_result.flag_category = "security_violation"

        if rule_results and rule_results.failed_checks:
            eval_result.checks_failed.extend(
                self._rule_to_behavior(c) for c in rule_results.failed_checks
            )

        eval_result.latency_ms = (time.time() - start_time) * 1000
        return eval_result

    @staticmethod
    def _rule_to_behavior(rule_check) -> BehaviorCheckResult:
        return BehaviorCheckResult(
            behavior=f"RULE: {rule_check.check_name}",
            passed=rule_check.passed,
            confidence=1.0,
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
        import asyncio

        last_error: Optional[Exception] = None
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
                    await asyncio.sleep(1.0 * (attempt + 1))

        logger.error("All evaluation attempts failed", error=str(last_error))
        return EvaluationResult(
            score=0.5,
            flagged=True,
            flag_reason=f"Evaluation failed after {max_retries + 1} attempts: {last_error}",
            flag_category="error",
        )

    async def quick_check(
        self,
        output_data: Any,
        node_config: Optional[NodeConfig] = None,
    ) -> dict[str, Any]:
        rule_results = self.rule_checker.check(None, output_data, node_config)
        return {
            "passed": not rule_results.critical_failure and not rule_results.failed_checks,
            "score": rule_results.score,
            "critical_failure": rule_results.critical_failure,
            "failure_reason": rule_results.failure_reason,
            "checks_failed": len(rule_results.failed_checks),
            "checks_passed": len(rule_results.passed_checks),
        }
