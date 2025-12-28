"""DSPy-based prompt optimization for improving failing prompts."""

import json
from typing import Any, Optional

import structlog

try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False

logger = structlog.get_logger()


class DSpyOptimizer:
    """
    Uses DSPy to optimize prompts that are producing unexpected behaviors.

    When evaluation flags an output, this optimizer can:
    1. Analyze the failure pattern
    2. Generate improved prompt variations using DSPy
    3. Test variations and track improvements
    4. Suggest the best performing prompt

    Features:
    - Automatic prompt refinement based on failure signatures
    - Few-shot example generation
    - Constraint injection for expected behaviors
    - A/B testing framework for prompt versions
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        api_key: Optional[str] = None,
    ):
        """
        Initialize the DSPy optimizer.

        Args:
            model_name: LLM model to use for optimization.
            api_key: API key for the model.
        """
        if not DSPY_AVAILABLE:
            logger.warning(
                "DSPy not installed. Install with: pip install dspy-ai"
            )
            self.enabled = False
            return

        self.model_name = model_name
        self.enabled = True
        self._optimization_history: list[dict[str, Any]] = []

        try:
            # Configure DSPy with Gemini via litellm
            # Format: gemini/model-name for litellm
            self.lm = dspy.LM(
                model=f"gemini/{model_name}",
                api_key=api_key,
                max_tokens=1024,
            )

            dspy.configure(lm=self.lm)
            logger.info("DSPy optimizer initialized", model=model_name)
        except Exception as e:
            logger.error("Failed to initialize DSPy", error=str(e))
            self.enabled = False

    async def optimize_prompt(
        self,
        original_prompt: str,
        failure_reason: str,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        failed_examples: list[dict[str, Any]],
        max_iterations: int = 3,
    ) -> dict[str, Any]:
        """
        Optimize a prompt that's producing failures.

        Args:
            original_prompt: The original prompt that failed.
            failure_reason: Description of why it failed.
            expected_behaviors: List of expected behaviors.
            unexpected_behaviors: List of behaviors to avoid.
            failed_examples: Examples of failures with input/output pairs.
            max_iterations: Maximum optimization iterations.

        Returns:
            Dictionary with:
            - improved_prompt: Optimized prompt
            - changes_made: List of improvements
            - confidence: Confidence score (0-1)
            - reasoning: Explanation of changes
        """
        if not self.enabled:
            return {
                "improved_prompt": original_prompt,
                "changes_made": [],
                "confidence": 0.0,
                "reasoning": "DSPy not available",
                "error": "DSPy not installed or failed to initialize",
            }

        try:
            # Build context for optimization
            context = self._build_optimization_context(
                original_prompt=original_prompt,
                failure_reason=failure_reason,
                expected_behaviors=expected_behaviors,
                unexpected_behaviors=unexpected_behaviors,
                failed_examples=failed_examples,
            )

            # Use DSPy ChainOfThought to generate improved prompt
            module = PromptImprovementModule()
            result = module(context=context)

            # Parse changes (comma-separated string to list)
            changes_list = [c.strip() for c in result.changes_made.split(',') if c.strip()]

            # Parse confidence
            try:
                confidence_val = float(result.confidence)
            except (ValueError, TypeError):
                confidence_val = 0.8  # Default

            # Track optimization
            optimization_record = {
                "original_prompt": original_prompt,
                "improved_prompt": result.improved_prompt,
                "failure_reason": failure_reason,
                "changes": changes_list,
                "confidence": confidence_val,
            }
            self._optimization_history.append(optimization_record)

            logger.info(
                "Prompt optimized",
                confidence=confidence_val,
                changes=len(changes_list),
            )

            return {
                "improved_prompt": result.improved_prompt,
                "changes_made": changes_list,
                "confidence": confidence_val,
                "reasoning": result.reasoning,
            }

        except Exception as e:
            logger.error("Prompt optimization failed", error=str(e))
            return {
                "improved_prompt": original_prompt,
                "changes_made": [],
                "confidence": 0.0,
                "reasoning": f"Optimization failed: {str(e)}",
                "error": str(e),
            }

    def _build_optimization_context(
        self,
        original_prompt: str,
        failure_reason: str,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        failed_examples: list[dict[str, Any]],
    ) -> str:
        """Build context string for prompt optimization."""
        context_parts = [
            f"Original Prompt:\n{original_prompt}\n",
            f"Failure Reason:\n{failure_reason}\n",
            f"Expected Behaviors:\n" + "\n".join(f"- {b}" for b in expected_behaviors),
            f"\nUnexpected Behaviors to Avoid:\n" + "\n".join(f"- {b}" for b in unexpected_behaviors),
        ]

        if failed_examples:
            context_parts.append("\nFailed Examples:")
            for i, example in enumerate(failed_examples[:3], 1):
                context_parts.append(
                    f"\nExample {i}:"
                    f"\nInput: {example.get('input', 'N/A')}"
                    f"\nOutput: {example.get('output', 'N/A')}"
                    f"\nIssue: {example.get('issue', 'N/A')}"
                )

        return "\n".join(context_parts)

    async def suggest_few_shot_examples(
        self,
        prompt: str,
        expected_behaviors: list[str],
        num_examples: int = 3,
    ) -> list[dict[str, str]]:
        """
        Generate few-shot examples to add to a prompt.

        Args:
            prompt: Base prompt.
            expected_behaviors: Expected output characteristics.
            num_examples: Number of examples to generate.

        Returns:
            List of input/output example pairs.
        """
        if not self.enabled:
            return []

        try:
            module = FewShotModule()
            result = module(
                prompt=prompt,
                behaviors=", ".join(expected_behaviors),
                num_examples=num_examples,
            )

            # Parse JSON string to list
            try:
                examples = json.loads(result.examples)
                return examples if isinstance(examples, list) else []
            except json.JSONDecodeError:
                return []

        except Exception as e:
            logger.error("Few-shot generation failed", error=str(e))
            return []

    async def analyze_failure_pattern(
        self,
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze a pattern of failures to identify root causes.

        Args:
            failures: List of failure records with evaluation results.

        Returns:
            Analysis with common patterns and suggested fixes.
        """
        if not self.enabled or not failures:
            return {"patterns": [], "suggestions": []}

        try:
            # Group failures by category
            by_category: dict[str, list] = {}
            for failure in failures:
                category = failure.get("category", "unknown")
                by_category.setdefault(category, []).append(failure)

            # Analyze each category
            patterns = []
            for category, examples in by_category.items():
                if len(examples) >= 2:  # Need multiple examples to identify pattern
                    patterns.append({
                        "category": category,
                        "frequency": len(examples),
                        "common_issues": self._extract_common_issues(examples),
                    })

            # Generate suggestions
            module = PatternAnalysisModule()
            result = module(
                patterns=json.dumps(patterns, indent=2),
                num_failures=len(failures),
            )

            # Parse comma-separated strings to lists
            suggestions_list = [s.strip() for s in result.suggestions.split(',') if s.strip()]
            root_causes_list = [r.strip() for r in result.root_causes.split(',') if r.strip()]

            return {
                "patterns": patterns,
                "suggestions": suggestions_list,
                "root_causes": root_causes_list,
            }

        except Exception as e:
            logger.error("Failure pattern analysis failed", error=str(e))
            return {"patterns": [], "suggestions": [], "error": str(e)}

    def _extract_common_issues(self, examples: list[dict[str, Any]]) -> list[str]:
        """Extract common issues from a set of failures."""
        issues = set()
        for example in examples:
            reason = example.get("flag_reason", "")
            if reason:
                issues.add(reason)
        return list(issues)[:5]  # Top 5 unique issues

    def get_optimization_history(self) -> list[dict[str, Any]]:
        """Get history of all prompt optimizations."""
        return self._optimization_history.copy()

    def clear_history(self) -> None:
        """Clear optimization history."""
        self._optimization_history.clear()


# DSPy Signatures and Modules (only defined if DSPy is available)
if DSPY_AVAILABLE:

    class PromptImprover(dspy.Signature):
        """Improve a prompt that's producing unexpected behaviors."""

        context: str = dspy.InputField(
            desc="Context including original prompt, failures, and desired behaviors"
        )
        improved_prompt: str = dspy.OutputField(
            desc="Improved version of the prompt with specific constraints"
        )
        changes_made: str = dspy.OutputField(
            desc="Comma-separated list of specific changes made"
        )
        confidence: float = dspy.OutputField(
            desc="Confidence score (0-1) that improvements will fix issues"
        )
        reasoning: str = dspy.OutputField(
            desc="Explanation of why these changes should improve the prompt"
        )

    class PromptImprovementModule(dspy.Module):
        """DSPy module for prompt improvement using ChainOfThought."""

        def __init__(self):
            super().__init__()
            self.improve = dspy.ChainOfThought(PromptImprover)

        def forward(self, context: str):
            """Improve prompt with reasoning."""
            result = self.improve(context=context)
            return result

    class FewShotGenerator(dspy.Signature):
        """Generate few-shot examples for a prompt."""

        prompt: str = dspy.InputField(desc="The prompt that needs examples")
        behaviors: str = dspy.InputField(desc="Expected output behaviors")
        num_examples: int = dspy.InputField(desc="Number of examples to generate")
        examples: str = dspy.OutputField(
            desc="List of input/output example pairs as JSON"
        )

    class FewShotModule(dspy.Module):
        """DSPy module for few-shot example generation."""

        def __init__(self):
            super().__init__()
            self.generate = dspy.Predict(FewShotGenerator)

        def forward(self, prompt: str, behaviors: str, num_examples: int):
            """Generate examples."""
            result = self.generate(prompt=prompt, behaviors=behaviors, num_examples=num_examples)
            return result

    class FailurePatternAnalyzer(dspy.Signature):
        """Analyze patterns in failures to identify root causes."""

        patterns: str = dspy.InputField(desc="Failure patterns grouped by category")
        num_failures: int = dspy.InputField(desc="Total number of failures")
        suggestions: str = dspy.OutputField(
            desc="Comma-separated list of suggestions to prevent failures"
        )
        root_causes: str = dspy.OutputField(
            desc="Identified root causes of the failure patterns"
        )

    class PatternAnalysisModule(dspy.Module):
        """DSPy module for failure pattern analysis."""

        def __init__(self):
            super().__init__()
            self.analyze = dspy.ChainOfThought(FailurePatternAnalyzer)

        def forward(self, patterns: str, num_failures: int):
            """Analyze patterns."""
            result = self.analyze(patterns=patterns, num_failures=num_failures)
            return result

else:
    # Dummy classes when DSPy not available
    PromptImprover = None
    PromptImprovementModule = None
    FewShotGenerator = None
    FewShotModule = None
    FailurePatternAnalyzer = None
    PatternAnalysisModule = None
