"""Failure classification utilities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FailureCategory(str, Enum):
    """Categories for LLM output failures."""
    HALLUCINATION = "hallucination"
    FORMAT_ERROR = "format_error"
    MISSING_CONTENT = "missing_content"
    SEMANTIC_DRIFT = "semantic_drift"
    INSTRUCTION_VIOLATION = "instruction_violation"
    SAFETY_VIOLATION = "safety_violation"
    CONTEXT_LOSS = "context_loss"
    REASONING_ERROR = "reasoning_error"
    SECURITY_VIOLATION = "security_violation"
    UNCLASSIFIED = "unclassified"


class FailureSeverity(str, Enum):
    """Severity levels for failures."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FailureClassification:
    """Result of failure classification."""
    category: FailureCategory
    severity: FailureSeverity
    reason: str
    remediation_hints: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_response: Optional[dict[str, Any]] = None

    @property
    def remediation_hint(self) -> Optional[str]:
        """Get first remediation hint (for backward compatibility)."""
        return self.remediation_hints[0] if self.remediation_hints else None


# Alias for backward compatibility
ClassificationResult = FailureClassification


class FailureClassifier:
    """
    Classifies LLM output failures into categories.

    Uses both rule-based heuristics and LLM-based classification
    for comprehensive failure analysis.
    """

    # Keywords associated with each category
    CATEGORY_KEYWORDS = {
        FailureCategory.HALLUCINATION: [
            "fabricated", "made up", "not in source", "invented",
            "hallucinated", "not found in", "does not exist",
        ],
        FailureCategory.FORMAT_ERROR: [
            "invalid json", "malformed", "parse error", "syntax error",
            "wrong format", "missing key", "type error",
        ],
        FailureCategory.MISSING_CONTENT: [
            "empty", "missing", "not provided", "absent", "omitted",
            "failed to include", "no response",
        ],
        FailureCategory.INSTRUCTION_VIOLATION: [
            "violated", "ignored instruction", "did not follow",
            "contrary to", "despite being asked",
        ],
        FailureCategory.SAFETY_VIOLATION: [
            "inappropriate", "harmful", "offensive", "dangerous",
            "unethical", "illegal",
        ],
        FailureCategory.CONTEXT_LOSS: [
            "ignored context", "lost context", "out of context",
            "irrelevant", "unrelated",
        ],
        FailureCategory.REASONING_ERROR: [
            "logical error", "incorrect conclusion", "faulty reasoning",
            "contradiction", "inconsistent",
        ],
    }

    def classify_from_checks(
        self,
        failed_checks: list[dict[str, Any]],
        input_data: Any = None,
        output_data: Any = None,
    ) -> FailureClassification:
        """
        Classify failure based on failed checks.

        Args:
            failed_checks: List of failed check results.
            input_data: Original input (for context).
            output_data: LLM output (for analysis).

        Returns:
            FailureClassification with category and details.
        """
        if not failed_checks:
            return FailureClassification(
                category=FailureCategory.UNCLASSIFIED,
                severity=FailureSeverity.LOW,
                reason="No failures to classify",
                confidence=1.0,
            )

        # Aggregate failure information
        all_reasons = []
        for check in failed_checks:
            if isinstance(check, dict):
                reason = check.get("reasoning") or check.get("message", "")
                behavior = check.get("behavior", "")
                all_reasons.append(f"{behavior}: {reason}")
            else:
                all_reasons.append(str(check))

        combined_text = " ".join(all_reasons).lower()

        # Score each category based on keyword matches
        category_scores: dict[FailureCategory, int] = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > 0:
                category_scores[category] = score

        # Determine best category
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            confidence = min(category_scores[best_category] / 3, 1.0)
        else:
            best_category = FailureCategory.UNCLASSIFIED
            confidence = 0.5

        # Determine severity based on category and check count
        severity = self._determine_severity(best_category, len(failed_checks))

        # Generate remediation hints
        hints = self._generate_hints(best_category)

        return FailureClassification(
            category=best_category,
            severity=severity,
            reason=self._summarize_failures(failed_checks),
            remediation_hints=hints,
            confidence=confidence,
        )

    def classify(
        self,
        failed_check: Any,
        input_data: Any = None,
        output_data: Any = None,
    ) -> FailureClassification:
        """
        Classify a single failed check.

        Args:
            failed_check: Single failed check (BehaviorCheckResult or dict).
            input_data: Original input (for context).
            output_data: LLM output (for analysis).

        Returns:
            FailureClassification with category and details.
        """
        # Convert single check to list format
        if hasattr(failed_check, "__dict__"):
            check_dict = {
                "behavior": getattr(failed_check, "behavior", ""),
                "reasoning": getattr(failed_check, "reasoning", ""),
                "message": getattr(failed_check, "message", ""),
                "passed": getattr(failed_check, "passed", False),
            }
        elif isinstance(failed_check, dict):
            check_dict = failed_check
        else:
            check_dict = {"reasoning": str(failed_check)}

        return self.classify_from_checks(
            failed_checks=[check_dict],
            input_data=input_data,
            output_data=output_data,
        )

    def classify_from_llm_response(
        self, response: dict[str, Any]
    ) -> FailureClassification:
        """
        Parse classification from LLM evaluation response.

        Args:
            response: LLM response dictionary.

        Returns:
            FailureClassification parsed from response.
        """
        category_str = response.get("category", "unclassified")
        try:
            category = FailureCategory(category_str)
        except ValueError:
            category = FailureCategory.UNCLASSIFIED

        severity_str = response.get("severity", "medium")
        severity_map = {
            "critical": FailureSeverity.CRITICAL,
            "high": FailureSeverity.HIGH,
            "medium": FailureSeverity.MEDIUM,
            "low": FailureSeverity.LOW,
        }
        severity = severity_map.get(severity_str, FailureSeverity.MEDIUM)

        return FailureClassification(
            category=category,
            severity=severity,
            reason=response.get("reason", "Unknown failure"),
            remediation_hints=response.get("remediation_hints", []),
            confidence=response.get("confidence", 0.5),
            raw_response=response,
        )

    def _determine_severity(
        self, category: FailureCategory, failure_count: int
    ) -> FailureSeverity:
        """Determine severity based on category and failure count."""
        # Categories with inherently high severity
        high_severity_categories = {
            FailureCategory.SAFETY_VIOLATION,
            FailureCategory.SECURITY_VIOLATION,
            FailureCategory.HALLUCINATION,
        }

        if category in high_severity_categories:
            return FailureSeverity.HIGH if failure_count == 1 else FailureSeverity.CRITICAL

        # Scale severity by failure count
        if failure_count >= 5:
            return FailureSeverity.CRITICAL
        elif failure_count >= 3:
            return FailureSeverity.HIGH
        elif failure_count >= 2:
            return FailureSeverity.MEDIUM
        else:
            return FailureSeverity.LOW

    def _summarize_failures(self, failed_checks: list[dict[str, Any]]) -> str:
        """Create a concise summary of failures."""
        if not failed_checks:
            return "No failures"

        if len(failed_checks) == 1:
            check = failed_checks[0]
            if isinstance(check, dict):
                return check.get("reasoning") or check.get("message", "Unknown failure")
            return str(check)

        return f"{len(failed_checks)} checks failed"

    def _generate_hints(self, category: FailureCategory) -> list[str]:
        """Generate remediation hints for a category."""
        hints_map = {
            FailureCategory.HALLUCINATION: [
                "Add explicit grounding instructions to the prompt",
                "Include source citations requirement",
                "Use retrieval-augmented generation",
            ],
            FailureCategory.FORMAT_ERROR: [
                "Provide clearer format examples in the prompt",
                "Use structured output schemas",
                "Add format validation before returning",
            ],
            FailureCategory.MISSING_CONTENT: [
                "Make requirements more explicit",
                "Add checklist of required elements",
                "Consider breaking into smaller prompts",
            ],
            FailureCategory.INSTRUCTION_VIOLATION: [
                "Emphasize key instructions more strongly",
                "Use system prompts for critical rules",
                "Add instruction reminder at end of prompt",
            ],
            FailureCategory.SAFETY_VIOLATION: [
                "Review and strengthen content filters",
                "Add explicit safety guidelines",
                "Consider input sanitization",
            ],
            FailureCategory.CONTEXT_LOSS: [
                "Reduce context length or summarize",
                "Place key information at start and end",
                "Use explicit context markers",
            ],
            FailureCategory.REASONING_ERROR: [
                "Add chain-of-thought prompting",
                "Break complex reasoning into steps",
                "Request explanation before conclusion",
            ],
        }

        return hints_map.get(category, ["Review prompt and expected behaviors"])
