"""Pluggable LLM judge protocol and result types."""

from detra.judges.base import BehaviorCheckResult, EvaluationResult, Judge

__all__ = ["BehaviorCheckResult", "EvaluationResult", "Judge"]
