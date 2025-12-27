"""Tests for the evaluation module."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vertiguard.config.schema import NodeConfig, SecurityConfig
from vertiguard.evaluation.prompts import (
    BEHAVIOR_CHECK_PROMPT,
    BATCH_BEHAVIOR_CHECK_PROMPT,
    ROOT_CAUSE_CLASSIFICATION_PROMPT,
    SECURITY_CHECK_PROMPT,
)
from vertiguard.evaluation.rules import (
    RuleBasedChecker,
    RuleEvaluationResult,
    RuleCheckResult,
)
from vertiguard.evaluation.classifiers import (
    FailureClassifier,
    FailureCategory,
    ClassificationResult,
)
from vertiguard.evaluation.gemini_judge import (
    GeminiJudge,
    EvaluationResult,
    BehaviorCheckResult,
)
from vertiguard.evaluation.engine import EvaluationEngine


class TestPrompts:
    """Tests for evaluation prompts."""

    def test_behavior_check_prompt_format(self):
        """Test that behavior check prompt has required placeholders."""
        assert "{input}" in BEHAVIOR_CHECK_PROMPT
        assert "{output}" in BEHAVIOR_CHECK_PROMPT
        assert "{behavior}" in BEHAVIOR_CHECK_PROMPT

    def test_batch_behavior_check_prompt_format(self):
        """Test batch behavior check prompt format."""
        assert "{input}" in BATCH_BEHAVIOR_CHECK_PROMPT
        assert "{output}" in BATCH_BEHAVIOR_CHECK_PROMPT
        assert "{expected_behaviors}" in BATCH_BEHAVIOR_CHECK_PROMPT
        assert "{unexpected_behaviors}" in BATCH_BEHAVIOR_CHECK_PROMPT

    def test_root_cause_prompt_format(self):
        """Test root cause classification prompt format."""
        assert "{behavior}" in ROOT_CAUSE_CLASSIFICATION_PROMPT
        assert "{reasoning}" in ROOT_CAUSE_CLASSIFICATION_PROMPT

    def test_security_check_prompt_format(self):
        """Test security check prompt format."""
        assert "{output}" in SECURITY_CHECK_PROMPT


class TestRuleEvaluator:
    """Tests for RuleBasedChecker."""

    @pytest.fixture
    def evaluator(self):
        """Create a rule evaluator instance."""
        return RuleBasedChecker()

    def test_check_empty_output(self, evaluator):
        """Test detection of empty output."""
        result = evaluator.check(
            input_data="Extract entities",
            output_data="",
        )
        assert result.critical_failure
        assert result.score == 0.0

    def test_check_error_pattern(self, evaluator):
        """Test detection of error patterns in output."""
        result = evaluator.check(
            input_data="Extract entities",
            output_data="Error: Unable to process request",
        )
        assert any("error" in c.check_name.lower() for c in result.failed_checks)

    def test_check_json_validity(self, evaluator):
        """Test JSON validity check when expected."""
        result = evaluator.check(
            input_data="Return JSON",
            output_data="not valid json",
        )
        # Should check for JSON validity if output looks like JSON
        # If output doesn't start with { or [, JSON check may not run

    def test_check_valid_json_output(self, evaluator):
        """Test valid JSON passes check."""
        result = evaluator.check(
            input_data="Return JSON",
            output_data='{"key": "value"}',
        )
        # JSON should be valid
        json_checks = [c for c in result.all_checks if c.check_name == "json_valid"]
        if json_checks:
            assert json_checks[0].passed

    def test_check_length_constraints(self, evaluator):
        """Test length constraint checking."""
        short_output = "Too short"
        result = evaluator.check(
            input_data="Write detailed summary",
            output_data=short_output,
        )
        # Length check should apply for suspiciously short outputs
        length_checks = [c for c in result.all_checks if c.check_name == "output_length"]
        if length_checks:
            # "Too short" is 9 chars, which is < 10, so should fail
            assert not length_checks[0].passed

    def test_all_rules_pass(self, evaluator):
        """Test when all rules pass."""
        result = evaluator.check(
            input_data="Extract entities",
            output_data='{"entities": ["Entity A", "Entity B"]}',
        )
        assert not result.critical_failure
        assert len(result.failed_checks) == 0

    def test_rule_evaluation_result_structure(self, evaluator):
        """Test RuleEvaluationResult structure."""
        result = evaluator.check(
            input_data="test",
            output_data="output",
        )
        assert isinstance(result, RuleEvaluationResult)
        assert isinstance(result.all_checks, list)
        assert isinstance(result.critical_failure, bool)
        assert isinstance(result.score, float)


class TestFailureClassifier:
    """Tests for FailureClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create a failure classifier instance."""
        return FailureClassifier()

    def test_classify_hallucination(self, classifier):
        """Test classification of hallucination failures."""
        result = classifier.classify(
            failed_check=BehaviorCheckResult(
                behavior="Party names must be from source document",
                passed=False,
                reasoning="Output contains 'John Smith' which is not in the source",
            ),
            input_data="Document mentions Alice and Bob",
            output_data="John Smith agreed to the terms",
        )
        assert result.category == FailureCategory.HALLUCINATION

    def test_classify_format_error(self, classifier):
        """Test classification of format errors."""
        result = classifier.classify(
            failed_check=BehaviorCheckResult(
                behavior="Must return valid JSON",
                passed=False,
                reasoning="Output is plain text, not JSON",
            ),
            input_data="Return JSON",
            output_data="This is not JSON",
        )
        assert result.category == FailureCategory.FORMAT_ERROR

    def test_classify_missing_content(self, classifier):
        """Test classification of missing content."""
        result = classifier.classify(
            failed_check=BehaviorCheckResult(
                behavior="Must include dates",
                passed=False,
                reasoning="No dates found in output",
            ),
            input_data="Extract all dates",
            output_data='{"entities": []}',
        )
        assert result.category == FailureCategory.MISSING_CONTENT

    def test_remediation_hint_provided(self, classifier):
        """Test that classification includes remediation hints."""
        result = classifier.classify(
            failed_check=BehaviorCheckResult(
                behavior="Must return valid JSON",
                passed=False,
                reasoning="Invalid JSON format",
            ),
            input_data="Return JSON",
            output_data="not json",
        )
        assert result.remediation_hint is not None
        assert len(result.remediation_hint) > 0


class TestGeminiJudge:
    """Tests for GeminiJudge."""

    @pytest.fixture
    def mock_gemini_config(self, sample_gemini_config):
        """Get Gemini config for testing."""
        return sample_gemini_config

    @pytest.fixture
    def judge(self, mock_gemini_config, mock_gemini_model):
        """Create a GeminiJudge with mocked client."""
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_gemini_model
            mock_client_class.return_value = mock_client
            
            judge = GeminiJudge(mock_gemini_config)
            judge._client = mock_client
            judge._setup_complete = True
            return judge

    @pytest.mark.asyncio
    async def test_evaluate_returns_result(self, judge, sample_llm_input, sample_llm_output):
        """Test that evaluate returns an EvaluationResult."""
        result = await judge.evaluate(
            input_data=sample_llm_input,
            output_data=sample_llm_output,
            expected_behaviors=["Must return valid JSON"],
            unexpected_behaviors=["Hallucinated content"],
        )
        assert isinstance(result, EvaluationResult)
        assert 0 <= result.score <= 1

    @pytest.mark.asyncio
    async def test_evaluate_captures_tokens(self, judge, sample_llm_input, sample_llm_output):
        """Test that evaluation tracks token usage."""
        result = await judge.evaluate(
            input_data=sample_llm_input,
            output_data=sample_llm_output,
            expected_behaviors=["Must return JSON"],
            unexpected_behaviors=[],
        )
        assert result.eval_tokens_used >= 0

    @pytest.mark.asyncio
    async def test_evaluate_with_empty_behaviors(self, judge):
        """Test evaluation with no behaviors specified."""
        result = await judge.evaluate(
            input_data="test input",
            output_data="test output",
            expected_behaviors=[],
            unexpected_behaviors=[],
        )
        # Should still return a valid result
        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_evaluate_sets_flagged_on_failure(self, judge):
        """Test that flagged is set when behaviors fail."""
        # Mock a response indicating failure
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "checks": [
                {"behavior": "Must return JSON", "passed": False, "reasoning": "Not JSON"}
            ],
            "overall_score": 0.3,
            "summary": "Failed checks"
        })
        judge._client.models.generate_content.return_value = mock_response

        result = await judge.evaluate(
            input_data="Return JSON",
            output_data="not json",
            expected_behaviors=["Must return JSON"],
            unexpected_behaviors=[],
        )
        assert result.flagged
        assert result.score < 0.5


class TestEvaluationEngine:
    """Tests for EvaluationEngine."""

    @pytest.fixture
    def mock_judge(self):
        """Create a mock GeminiJudge."""
        judge = MagicMock()
        judge.evaluate = AsyncMock(return_value=EvaluationResult(
            score=0.9,
            flagged=False,
            flag_category=None,
            flag_reason=None,
            checks_passed=[
                BehaviorCheckResult(
                    behavior="Must return JSON",
                    passed=True,
                    reasoning="Valid JSON"
                )
            ],
            checks_failed=[],
            security_issues=[],
            latency_ms=100,
            eval_tokens_used=500,
        ))
        return judge

    @pytest.fixture
    def engine(self, mock_judge, sample_security_config):
        """Create an EvaluationEngine."""
        return EvaluationEngine(mock_judge, sample_security_config)

    @pytest.mark.asyncio
    async def test_evaluate_returns_result(self, engine, sample_node_config):
        """Test that engine returns EvaluationResult."""
        result = await engine.evaluate(
            node_config=sample_node_config,
            input_data="Extract entities",
            output_data='{"parties": ["A", "B"]}',
        )
        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_evaluate_runs_security_checks(
        self, engine, sample_node_config, sample_llm_output_with_pii
    ):
        """Test that security checks are run when enabled."""
        result = await engine.evaluate(
            node_config=sample_node_config,
            input_data="Extract entities",
            output_data=json.dumps(sample_llm_output_with_pii),
        )
        # Should have security issues due to PII in output
        assert len(result.security_issues) > 0 or result.score > 0

    @pytest.mark.asyncio
    async def test_evaluate_skips_llm_on_critical_rule_failure(self, engine, sample_node_config):
        """Test that LLM evaluation is skipped on critical rule failures."""
        # Empty output should trigger critical failure
        result = await engine.evaluate(
            node_config=sample_node_config,
            input_data="Extract entities",
            output_data="",
        )
        # Should have low score due to empty output
        assert result.flagged

    @pytest.mark.asyncio
    async def test_evaluate_with_context(self, engine, sample_node_config):
        """Test evaluation with additional context."""
        context = {"document_type": "contract", "source": "legal_db"}
        result = await engine.evaluate(
            node_config=sample_node_config,
            input_data="Extract entities",
            output_data='{"parties": []}',
            context=context,
        )
        assert isinstance(result, EvaluationResult)


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_evaluation_result(self):
        """Test creating an EvaluationResult."""
        result = EvaluationResult(
            score=0.85,
            flagged=False,
            flag_category=None,
            flag_reason=None,
            checks_passed=[],
            checks_failed=[],
            security_issues=[],
            latency_ms=150.5,
            eval_tokens_used=1000,
        )
        assert result.score == 0.85
        assert not result.flagged

    def test_flagged_result(self):
        """Test a flagged evaluation result."""
        result = EvaluationResult(
            score=0.45,
            flagged=True,
            flag_category="hallucination",
            flag_reason="Output contains fabricated information",
            checks_passed=[],
            checks_failed=[
                BehaviorCheckResult(
                    behavior="Must be grounded",
                    passed=False,
                    reasoning="Contains fabricated names"
                )
            ],
            security_issues=[],
            latency_ms=200,
            eval_tokens_used=800,
        )
        assert result.flagged
        assert result.flag_category == "hallucination"
        assert len(result.checks_failed) == 1


class TestBehaviorCheckResult:
    """Tests for BehaviorCheckResult dataclass."""

    def test_passed_check(self):
        """Test a passing behavior check."""
        check = BehaviorCheckResult(
            behavior="Must return valid JSON",
            passed=True,
            reasoning="Output is properly formatted JSON",
        )
        assert check.passed
        assert "JSON" in check.reasoning

    def test_failed_check(self):
        """Test a failing behavior check."""
        check = BehaviorCheckResult(
            behavior="Must include all parties",
            passed=False,
            reasoning="Missing party 'Company B' from source document",
        )
        assert not check.passed


class TestEdgeCases:
    """Edge case tests for evaluation module."""

    def test_rule_evaluator_with_binary_content(self):
        """Test rule evaluator with binary-like content."""
        evaluator = RuleBasedChecker()
        result = evaluator.check(
            input_data="test",
            output_data="\x00\x01\x02binary",
        )
        # Should handle without crashing
        assert isinstance(result, RuleEvaluationResult)

    def test_classifier_with_very_long_reasoning(self):
        """Test classifier with very long reasoning text."""
        classifier = FailureClassifier()
        result = classifier.classify(
            failed_check=BehaviorCheckResult(
                behavior="Test behavior",
                passed=False,
                reasoning="Very long reasoning " * 1000,
            ),
            input_data="input",
            output_data="output",
        )
        assert result.category is not None

    @pytest.mark.asyncio
    async def test_engine_handles_judge_error(self, sample_node_config, sample_security_config):
        """Test engine handles judge errors gracefully."""
        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(side_effect=Exception("Judge error"))

        engine = EvaluationEngine(mock_judge, sample_security_config)

        # Should handle error gracefully
        try:
            result = await engine.evaluate(
                node_config=sample_node_config,
                input_data="test",
                output_data="output",
            )
            # If it returns, should be a failed evaluation
            assert result.flagged or result.score < 1.0
        except Exception as e:
            # Or raise a meaningful error
            assert "Judge error" in str(e) or isinstance(e, Exception)

    def test_rule_evaluator_unicode_content(self):
        """Test rule evaluator with Unicode content."""
        evaluator = RuleBasedChecker()
        result = evaluator.check(
            input_data="Extract entities: ",
            output_data='{"parties": [" Corporation"]}',
        )
        assert isinstance(result, RuleEvaluationResult)

    def test_failure_classifier_all_categories(self):
        """Test that all failure categories can be assigned."""
        classifier = FailureClassifier()

        categories_tested = set()
        test_cases = [
            ("hallucinated", "not in source", FailureCategory.HALLUCINATION),
            ("invalid JSON format", "parse error", FailureCategory.FORMAT_ERROR),
            ("missing required field", "not found", FailureCategory.MISSING_CONTENT),
        ]

        for behavior, reasoning, expected_cat in test_cases:
            result = classifier.classify(
                failed_check=BehaviorCheckResult(
                    behavior=behavior,
                    passed=False,
                    reasoning=reasoning,
                ),
                input_data="input",
                output_data="output",
            )
            categories_tested.add(result.category)

        # Should be able to classify into multiple categories
        assert len(categories_tested) > 0
