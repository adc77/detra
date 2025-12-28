"""Fast rule-based evaluation checks."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from detra.config.schema import NodeConfig


class RuleSeverity(str, Enum):
    """Severity levels for rule check failures."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"


@dataclass
class RuleCheckResult:
    """Result of a single rule check."""
    check_name: str
    passed: bool
    severity: RuleSeverity
    message: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleEvaluationResult:
    """Result of all rule-based checks."""
    score: float
    critical_failure: bool
    passed_checks: list[RuleCheckResult] = field(default_factory=list)
    failed_checks: list[RuleCheckResult] = field(default_factory=list)
    failure_reason: Optional[str] = None
    failure_category: Optional[str] = None

    @property
    def all_checks(self) -> list[RuleCheckResult]:
        """Get all checks."""
        return self.passed_checks + self.failed_checks


class RuleBasedChecker:
    """
    Fast, deterministic rule-based checks before LLM evaluation.

    These checks run quickly and can short-circuit expensive
    LLM evaluations for obvious failures.
    """

    # Error patterns that indicate LLM refusal or errors
    ERROR_PATTERNS = [
        (r"(?i)error:", RuleSeverity.HIGH),
        (r"(?i)exception:", RuleSeverity.HIGH),
        (r"(?i)i cannot", RuleSeverity.MEDIUM),
        (r"(?i)i'm unable to", RuleSeverity.MEDIUM),
        (r"(?i)as an ai", RuleSeverity.LOW),
        (r"(?i)i don't have access", RuleSeverity.MEDIUM),
        (r"(?i)i apologize", RuleSeverity.LOW),
    ]

    def check(
        self,
        input_data: Any,
        output_data: Any,
        node_config: Optional[NodeConfig] = None,
    ) -> RuleEvaluationResult:
        """
        Run all applicable rule-based checks.

        Args:
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            node_config: Node-specific configuration.

        Returns:
            RuleEvaluationResult with all check results.
        """
        output_str = str(output_data) if output_data else ""

        result = RuleEvaluationResult(
            score=1.0,
            critical_failure=False,
        )

        # Check for empty output (critical failure)
        empty_check = self._check_empty_output(output_str)
        if not empty_check.passed:
            result.critical_failure = True
            result.score = 0.0
            result.failure_reason = empty_check.message
            result.failure_category = "missing_content"
            result.failed_checks.append(empty_check)
            return result

        result.passed_checks.append(empty_check)

        # Check for error patterns
        for pattern, severity in self.ERROR_PATTERNS:
            check_result = self._check_error_pattern(output_str, pattern, severity)
            if not check_result.passed:
                result.failed_checks.append(check_result)
            else:
                result.passed_checks.append(check_result)

        # Check JSON validity if output looks like JSON
        json_check = self._check_json_validity(output_str)
        if json_check:
            if json_check.passed:
                result.passed_checks.append(json_check)
            else:
                result.failed_checks.append(json_check)
                result.score -= 0.2

        # Check output length
        length_check = self._check_output_length(output_str)
        if not length_check.passed:
            result.failed_checks.append(length_check)
            if length_check.severity == RuleSeverity.MEDIUM:
                result.score -= 0.1

        # Calculate final score based on failures
        failure_count = len(result.failed_checks)
        if failure_count > 0:
            penalty = 0.1 * failure_count
            result.score = max(0.0, result.score - penalty)

        return result

    def _check_empty_output(self, output_str: str) -> RuleCheckResult:
        """Check for empty or whitespace-only output."""
        if not output_str or output_str.strip() == "":
            return RuleCheckResult(
                check_name="empty_output",
                passed=False,
                severity=RuleSeverity.CRITICAL,
                message="Empty output",
            )
        return RuleCheckResult(
            check_name="empty_output",
            passed=True,
            severity=RuleSeverity.CRITICAL,
        )

    def _check_error_pattern(
        self, output_str: str, pattern: str, severity: RuleSeverity
    ) -> RuleCheckResult:
        """Check for error patterns in output."""
        match = re.search(pattern, output_str)
        check_name = f"error_pattern_{pattern[:20]}"

        if match:
            return RuleCheckResult(
                check_name=check_name,
                passed=False,
                severity=severity,
                message=f"Error pattern detected: {pattern}",
                details={"matched_text": match.group()},
            )
        return RuleCheckResult(
            check_name=check_name,
            passed=True,
            severity=severity,
        )

    def _check_json_validity(self, output_str: str) -> Optional[RuleCheckResult]:
        """Check JSON validity if output appears to be JSON."""
        stripped = output_str.strip()

        # Only check if it looks like JSON
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return None

        # Handle markdown code blocks
        if "```json" in stripped or "```" in stripped:
            # Extract JSON from code block
            if "```json" in stripped:
                start = stripped.find("```json") + 7
            else:
                start = stripped.find("```") + 3
            end = stripped.rfind("```")
            if end > start:
                stripped = stripped[start:end].strip()

        try:
            json.loads(stripped)
            return RuleCheckResult(
                check_name="json_valid",
                passed=True,
                severity=RuleSeverity.HIGH,
            )
        except json.JSONDecodeError as e:
            return RuleCheckResult(
                check_name="json_valid",
                passed=False,
                severity=RuleSeverity.HIGH,
                message=f"Invalid JSON: {str(e)}",
                details={"error": str(e)},
            )

    def _check_output_length(self, output_str: str) -> RuleCheckResult:
        """Check output length for anomalies."""
        length = len(output_str)

        if length < 10:
            return RuleCheckResult(
                check_name="output_length",
                passed=False,
                severity=RuleSeverity.MEDIUM,
                message=f"Output suspiciously short: {length} chars",
                details={"length": length},
            )

        if length > 50000:
            return RuleCheckResult(
                check_name="output_length",
                passed=False,
                severity=RuleSeverity.WARNING,
                message=f"Output unusually long: {length} chars",
                details={"length": length},
            )

        return RuleCheckResult(
            check_name="output_length",
            passed=True,
            severity=RuleSeverity.LOW,
            details={"length": length},
        )

    def check_format_requirements(
        self,
        output_str: str,
        requirements: dict[str, Any],
    ) -> list[RuleCheckResult]:
        """
        Check output against format requirements.

        Args:
            output_str: Output to check.
            requirements: Format requirements (e.g., max_length, required_keys).

        Returns:
            List of check results.
        """
        results = []

        if "max_length" in requirements:
            max_len = requirements["max_length"]
            if len(output_str) > max_len:
                results.append(
                    RuleCheckResult(
                        check_name="max_length",
                        passed=False,
                        severity=RuleSeverity.MEDIUM,
                        message=f"Output exceeds max length: {len(output_str)} > {max_len}",
                    )
                )

        if "required_keys" in requirements:
            try:
                data = json.loads(output_str)
                for key in requirements["required_keys"]:
                    if key not in data:
                        results.append(
                            RuleCheckResult(
                                check_name=f"required_key_{key}",
                                passed=False,
                                severity=RuleSeverity.HIGH,
                                message=f"Missing required key: {key}",
                            )
                        )
            except json.JSONDecodeError:
                pass  # Already handled by JSON validity check

        if "must_contain" in requirements:
            for phrase in requirements["must_contain"]:
                if phrase.lower() not in output_str.lower():
                    results.append(
                        RuleCheckResult(
                            check_name=f"must_contain_{phrase[:20]}",
                            passed=False,
                            severity=RuleSeverity.MEDIUM,
                            message=f"Missing required content: {phrase}",
                        )
                    )

        if "must_not_contain" in requirements:
            for phrase in requirements["must_not_contain"]:
                if phrase.lower() in output_str.lower():
                    results.append(
                        RuleCheckResult(
                            check_name=f"must_not_contain_{phrase[:20]}",
                            passed=False,
                            severity=RuleSeverity.HIGH,
                            message=f"Contains forbidden content: {phrase}",
                        )
                    )

        return results
