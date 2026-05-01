"""Judge protocol and shared result types.

Every judge must satisfy the ``Judge`` protocol.  The two dataclasses
(``BehaviorCheckResult``, ``EvaluationResult``) are the canonical return
types used across the evaluation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class BehaviorCheckResult:
    """Result of checking a single expected/unexpected behavior."""

    behavior: str
    passed: bool
    reasoning: str
    confidence: float = 0.0
    evidence: Optional[str] = None


@dataclass
class EvaluationResult:
    """Aggregate result of a full evaluation pass."""

    score: float
    flagged: bool
    flag_reason: Optional[str] = None
    flag_category: Optional[str] = None
    checks_passed: list[BehaviorCheckResult] = field(default_factory=list)
    checks_failed: list[BehaviorCheckResult] = field(default_factory=list)
    security_issues: list[dict[str, Any]] = field(default_factory=list)
    raw_evaluation: Optional[dict[str, Any]] = None
    latency_ms: float = 0.0
    eval_tokens_used: int = 0


@runtime_checkable
class Judge(Protocol):
    """Structural interface that every LLM judge must satisfy.

    Provide ``evaluate_behaviors`` for behavior-based scoring and
    ``check_security`` for LLM-assisted security scans.  Any object
    with these two async methods is a valid judge -- no subclassing needed.
    """

    async def evaluate_behaviors(
        self,
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        context: dict[str, Any] | None = None,
    ) -> EvaluationResult: ...

    async def check_security(
        self,
        input_data: Any,
        output_data: Any,
        checks: list[str],
    ) -> list[dict[str, Any]]: ...
