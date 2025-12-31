"""DSPy-based prompt optimization for improving failing prompts."""

import asyncio
import json
import re
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
        model_name: str = "gemini-2.5-flash",
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
        self._modules_cache: dict[str, Any] = {}  # Cache modules for reuse

        try:
            # Configure DSPy with Gemini via litellm
            # Format: gemini/model-name for litellm
            self.lm = dspy.LM(
                model=f"gemini/{model_name}",
                api_key=api_key,
                max_tokens=2048,  # Increased for better responses
            )

            # Try modern API first, fallback to legacy
            try:
                # Modern DSPy uses dspy.settings
                if hasattr(dspy, 'settings'):
                    dspy.settings.configure(lm=self.lm)
                else:
                    dspy.configure(lm=self.lm)
            except AttributeError:
                # Fallback to legacy API
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
            max_iterations: Maximum optimization iterations (now implemented).

        Returns:
            Dictionary with:
            - improved_prompt: Optimized prompt
            - changes_made: List of improvements
            - confidence: Confidence score (0-1)
            - reasoning: Explanation of changes
            - iterations: Number of iterations performed
        """
        if not self.enabled:
            return {
                "improved_prompt": original_prompt,
                "changes_made": [],
                "confidence": 0.0,
                "reasoning": "DSPy not available",
                "error": "DSPy not installed or failed to initialize",
                "iterations": 0,
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

            # Iterative optimization: try multiple iterations to improve the prompt
            best_result = None
            best_confidence = 0.0
            current_prompt = original_prompt

            for iteration in range(1, max_iterations + 1):
                # Run DSPy module in executor to avoid blocking event loop
                result = await self._run_dspy_module_async(
                    "prompt_improvement",
                    context=context,
                )

                if not result:
                    logger.warning(f"Optimization iteration {iteration} returned no result")
                    break

                # Parse and validate result
                parsed_result = self._parse_optimization_result(result)
                if not parsed_result:
                    logger.warning(f"Failed to parse result from iteration {iteration}")
                    break

                # Update best result if confidence improved
                if parsed_result["confidence"] > best_confidence:
                    best_confidence = parsed_result["confidence"]
                    best_result = parsed_result
                    current_prompt = parsed_result["improved_prompt"]

                # Early exit if confidence is very high
                if best_confidence >= 0.95:
                    logger.info(f"High confidence reached at iteration {iteration}, stopping early")
                    break

                # Update context for next iteration with improved prompt
                if iteration < max_iterations:
                    context = self._build_optimization_context(
                        original_prompt=original_prompt,
                        failure_reason=failure_reason,
                        expected_behaviors=expected_behaviors,
                        unexpected_behaviors=unexpected_behaviors,
                        failed_examples=failed_examples,
                        previous_attempt=current_prompt,
                    )

            # Use best result or fallback to original
            if best_result:
                optimization_record = {
                    "original_prompt": original_prompt,
                    "improved_prompt": best_result["improved_prompt"],
                    "failure_reason": failure_reason,
                    "changes": best_result["changes_made"],
                    "confidence": best_result["confidence"],
                    "iterations": iteration,
                }
                self._optimization_history.append(optimization_record)

                logger.info(
                    "Prompt optimized",
                    confidence=best_result["confidence"],
                    changes=len(best_result["changes_made"]),
                    iterations=iteration,
                )

                return {
                    **best_result,
                    "iterations": iteration,
                }
            else:
                # Fallback: return original prompt if all iterations failed
                logger.warning("All optimization iterations failed, returning original prompt")
                return {
                    "improved_prompt": original_prompt,
                    "changes_made": [],
                    "confidence": 0.0,
                    "reasoning": "All optimization iterations failed",
                    "iterations": 0,
                    "error": "Optimization failed",
                }

        except Exception as e:
            logger.error("Prompt optimization failed", error=str(e), exc_info=True)
            return {
                "improved_prompt": original_prompt,
                "changes_made": [],
                "confidence": 0.0,
                "reasoning": f"Optimization failed: {str(e)}",
                "error": str(e),
                "iterations": 0,
            }

    def _build_optimization_context(
        self,
        original_prompt: str,
        failure_reason: str,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        failed_examples: list[dict[str, Any]],
        previous_attempt: Optional[str] = None,
    ) -> str:
        """Build context string for prompt optimization."""
        context_parts = [
            f"Original Prompt:\n{original_prompt}\n",
            f"Failure Reason:\n{failure_reason}\n",
            f"Expected Behaviors:\n" + "\n".join(f"- {b}" for b in expected_behaviors),
            f"\nUnexpected Behaviors to Avoid:\n" + "\n".join(f"- {b}" for b in unexpected_behaviors),
        ]

        if previous_attempt:
            context_parts.append(
                f"\nPrevious Optimization Attempt:\n{previous_attempt}\n"
                f"(This attempt did not fully resolve the issues. Please try a different approach.)"
            )

        if failed_examples:
            context_parts.append("\nFailed Examples:")
            for i, example in enumerate(failed_examples[:5], 1):  # Show up to 5 examples
                context_parts.append(
                    f"\nExample {i}:"
                    f"\nInput: {example.get('input', 'N/A')}"
                    f"\nOutput: {example.get('output', 'N/A')}"
                    f"\nIssue: {example.get('issue', 'N/A')}"
                )

        return "\n".join(context_parts)

    def _run_dspy_module_sync(
        self,
        module_type: str,
        **kwargs: Any,
    ) -> Any:
        """Synchronous helper to run DSPy modules."""
        try:
            # Get or create module from cache
            if module_type not in self._modules_cache:
                if module_type == "prompt_improvement":
                    self._modules_cache[module_type] = PromptImprovementModule()
                elif module_type == "few_shot":
                    self._modules_cache[module_type] = FewShotModule()
                elif module_type == "pattern_analysis":
                    self._modules_cache[module_type] = PatternAnalysisModule()
                else:
                    raise ValueError(f"Unknown module type: {module_type}")

            module = self._modules_cache[module_type]

            # Run the module
            if module_type == "prompt_improvement":
                return module(context=kwargs["context"])
            elif module_type == "few_shot":
                return module(
                    prompt=kwargs["prompt"],
                    behaviors=kwargs["behaviors"],
                    num_examples=kwargs["num_examples"],
                )
            elif module_type == "pattern_analysis":
                return module(
                    patterns=kwargs["patterns"],
                    num_failures=kwargs["num_failures"],
                )
            else:
                raise ValueError(f"Unknown module type: {module_type}")

        except Exception as e:
            logger.error(f"DSPy module execution failed", module_type=module_type, error=str(e))
            raise

    async def _run_dspy_module_async(
        self,
        module_type: str,
        **kwargs: Any,
    ) -> Any:
        """Run DSPy module asynchronously using executor."""
        return await asyncio.to_thread(self._run_dspy_module_sync, module_type, **kwargs)

    def _parse_optimization_result(self, result: Any) -> Optional[dict[str, Any]]:
        """Parse and validate DSPy optimization result."""
        try:
            if not result or not hasattr(result, "improved_prompt"):
                return None

            # Extract improved prompt
            improved_prompt = str(result.improved_prompt).strip()
            if not improved_prompt:
                return None

            # Parse changes (handle various formats)
            changes_str = str(result.changes_made) if hasattr(result, "changes_made") else ""
            changes_list = self._parse_changes_list(changes_str)

            # Parse confidence (handle various formats)
            confidence_val = self._parse_confidence(result)

            # Extract reasoning
            reasoning = str(result.reasoning).strip() if hasattr(result, "reasoning") else ""

            return {
                "improved_prompt": improved_prompt,
                "changes_made": changes_list,
                "confidence": confidence_val,
                "reasoning": reasoning,
            }

        except Exception as e:
            logger.error("Failed to parse optimization result", error=str(e))
            return None

    def _parse_changes_list(self, changes_str: str) -> list[str]:
        """Parse changes list from various formats."""
        if not changes_str:
            return []

        # Try comma-separated first
        if "," in changes_str:
            return [c.strip() for c in changes_str.split(",") if c.strip()]

        # Try newline-separated
        if "\n" in changes_str:
            return [c.strip() for c in changes_str.split("\n") if c.strip()]

        # Try numbered list (1., 2., etc.)
        numbered_pattern = r"\d+[\.\)]\s*(.+?)(?=\d+[\.\)]|$)"
        matches = re.findall(numbered_pattern, changes_str, re.DOTALL)
        if matches:
            return [m.strip() for m in matches if m.strip()]

        # Try bullet points (-, *, •)
        bullet_pattern = r"[-\*•]\s*(.+?)(?=[-\*•]|$)"
        matches = re.findall(bullet_pattern, changes_str, re.DOTALL)
        if matches:
            return [m.strip() for m in matches if m.strip()]

        # Fallback: return as single item if non-empty
        return [changes_str.strip()] if changes_str.strip() else []

    def _parse_confidence(self, result: Any) -> float:
        """Parse confidence value from result, handling various formats."""
        if not hasattr(result, "confidence"):
            return 0.8  # Default

        confidence = result.confidence

        # If it's already a number
        if isinstance(confidence, (int, float)):
            return max(0.0, min(1.0, float(confidence)))

        # Try to extract number from string
        confidence_str = str(confidence).strip()
        if not confidence_str:
            return 0.8

        # Extract number (handles "0.85", "85%", "85", etc.)
        number_match = re.search(r"(\d+\.?\d*)", confidence_str)
        if number_match:
            num = float(number_match.group(1))
            # If > 1, assume it's a percentage
            if num > 1:
                num = num / 100.0
            return max(0.0, min(1.0, num))

        return 0.8  # Default fallback

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
            # Run in executor to avoid blocking
            result = await self._run_dspy_module_async(
                "few_shot",
                prompt=prompt,
                behaviors=", ".join(expected_behaviors),
                num_examples=num_examples,
            )

            if not result or not hasattr(result, "examples"):
                return []

            # Parse JSON string to list
            examples_str = str(result.examples).strip()
            if not examples_str:
                return []

            # Try to parse as JSON
            try:
                examples = json.loads(examples_str)
                if isinstance(examples, list):
                    # Validate structure
                    validated = []
                    for ex in examples:
                        if isinstance(ex, dict) and ("input" in ex or "query" in ex):
                            validated.append(ex)
                    return validated[:num_examples]
                return []
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", examples_str, re.DOTALL)
                if json_match:
                    try:
                        examples = json.loads(json_match.group(1))
                        return examples if isinstance(examples, list) else []
                    except json.JSONDecodeError:
                        pass
                return []

        except Exception as e:
            logger.error("Few-shot generation failed", error=str(e), exc_info=True)
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
            return {"patterns": [], "suggestions": [], "root_causes": []}

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

            if not patterns:
                return {"patterns": [], "suggestions": [], "root_causes": []}

            # Run in executor to avoid blocking
            result = await self._run_dspy_module_async(
                "pattern_analysis",
                patterns=json.dumps(patterns, indent=2),
                num_failures=len(failures),
            )

            if not result:
                return {"patterns": patterns, "suggestions": [], "root_causes": []}

            # Parse comma-separated strings to lists with better parsing
            suggestions_str = str(result.suggestions) if hasattr(result, "suggestions") else ""
            root_causes_str = str(result.root_causes) if hasattr(result, "root_causes") else ""

            suggestions_list = self._parse_changes_list(suggestions_str)
            root_causes_list = self._parse_changes_list(root_causes_str)

            return {
                "patterns": patterns,
                "suggestions": suggestions_list,
                "root_causes": root_causes_list,
            }

        except Exception as e:
            logger.error("Failure pattern analysis failed", error=str(e), exc_info=True)
            return {"patterns": [], "suggestions": [], "root_causes": [], "error": str(e)}

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
