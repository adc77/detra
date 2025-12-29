"""LLM-based root cause analysis for errors and failures."""

import json
from typing import Any, Optional

import google.genai as genai
import structlog

logger = structlog.get_logger()


class RootCauseAnalyzer:
    """
    Uses LLM to analyze errors and provide actionable root cause analysis.

    When an error or unexpected behavior occurs, this analyzer:
    1. Analyzes the error context (stack trace, inputs, outputs)
    2. Identifies potential root causes
    3. Suggests specific fixes with file/code references
    4. Provides debugging steps

    This gives developers immediate, contextual guidance on how to fix issues.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
    ):
        """
        Initialize the root cause analyzer.

        Args:
            api_key: Google API key for Gemini.
            model: Gemini model to use.
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._analysis_cache: dict[str, dict[str, Any]] = {}

        logger.info("Root cause analyzer initialized", model=model)

    async def analyze_error(
        self,
        error: Exception,
        context: dict[str, Any],
        node_name: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Analyze an error and provide root cause analysis.

        Args:
            error: The exception that occurred.
            context: Additional context about the error.
            node_name: Name of the node where error occurred.
            input_data: Input that caused the error.
            output_data: Output (if any) before error.

        Returns:
            Dictionary with:
            - root_cause: Identified root cause
            - suggested_fixes: List of specific fixes
            - files_to_check: Files that may need changes
            - debug_steps: Steps to debug the issue
            - severity: Error severity (critical/high/medium/low)
        """
        try:
            # Build error context
            error_context = self._build_error_context(
                error=error,
                context=context,
                node_name=node_name,
                input_data=input_data,
                output_data=output_data,
            )

            # Check cache
            cache_key = self._get_cache_key(error)
            if cache_key in self._analysis_cache:
                logger.debug("Using cached root cause analysis")
                return self._analysis_cache[cache_key]

            # Analyze with LLM
            analysis = await self._run_analysis(error_context)

            # Cache result
            self._analysis_cache[cache_key] = analysis

            logger.info(
                "Root cause analysis complete",
                root_cause=analysis.get("root_cause", "Unknown"),
                severity=analysis.get("severity", "medium"),
            )

            return analysis

        except Exception as e:
            logger.error("Root cause analysis failed", error=str(e))
            return {
                "root_cause": "Analysis failed",
                "suggested_fixes": ["Manual investigation required"],
                "files_to_check": [],
                "debug_steps": ["Review error logs", "Check input data"],
                "severity": "unknown",
                "error": str(e),
            }

    async def analyze_evaluation_failure(
        self,
        node_name: str,
        score: float,
        failed_behaviors: list[str],
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        node_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Analyze an evaluation failure (low adherence score).

        Args:
            node_name: Name of the failing node.
            score: Adherence score.
            failed_behaviors: List of behaviors that failed.
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            expected_behaviors: Expected behaviors.
            node_config: Node configuration.

        Returns:
            Root cause analysis with suggested prompt improvements.
        """
        try:
            # Build evaluation failure context
            context = self._build_evaluation_context(
                node_name=node_name,
                score=score,
                failed_behaviors=failed_behaviors,
                input_data=input_data,
                output_data=output_data,
                expected_behaviors=expected_behaviors,
                node_config=node_config,
            )

            # Analyze with LLM
            analysis = await self._run_evaluation_analysis(context)

            logger.info(
                "Evaluation failure analyzed",
                node=node_name,
                score=score,
                suggestions=len(analysis.get("suggested_fixes", [])),
            )

            return analysis

        except Exception as e:
            logger.error("Evaluation analysis failed", error=str(e))
            return {
                "root_cause": "Analysis failed",
                "suggested_fixes": [],
                "prompt_improvements": [],
                "severity": "medium",
                "error": str(e),
            }

    def _build_error_context(
        self,
        error: Exception,
        context: dict[str, Any],
        node_name: Optional[str],
        input_data: Any,
        output_data: Any,
    ) -> str:
        """Build context string for error analysis."""
        parts = [
            "# Error Analysis Request\n",
            f"## Error Type: {type(error).__name__}",
            f"## Error Message: {str(error)}\n",
        ]

        if node_name:
            parts.append(f"## Node: {node_name}\n")

        # Add stack trace if available
        import traceback
        stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        parts.append(f"## Stack Trace:\n```\n{stack_trace}\n```\n")

        # Add input/output context
        if input_data:
            parts.append(f"## Input Data:\n```\n{self._truncate(str(input_data), 500)}\n```\n")

        if output_data:
            parts.append(f"## Output Data (if any):\n```\n{self._truncate(str(output_data), 500)}\n```\n")

        # Add additional context
        if context:
            parts.append(f"## Additional Context:\n{json.dumps(context, indent=2)}\n")

        parts.append("\n## Analysis Instructions:")
        parts.append("Analyze this error and provide:")
        parts.append("1. Root cause (be specific)")
        parts.append("2. 3-5 suggested fixes (actionable, specific)")
        parts.append("3. Files or code areas to check")
        parts.append("4. Debug steps to reproduce/investigate")
        parts.append("5. Severity assessment (critical/high/medium/low)")

        return "\n".join(parts)

    def _build_evaluation_context(
        self,
        node_name: str,
        score: float,
        failed_behaviors: list[str],
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        node_config: Optional[dict[str, Any]],
    ) -> str:
        """Build context for evaluation failure analysis."""
        parts = [
            "# Evaluation Failure Analysis\n",
            f"## Node: {node_name}",
            f"## Adherence Score: {score:.2f}\n",
            f"## Failed Behaviors:\n" + "\n".join(f"- {b}" for b in failed_behaviors),
            f"\n## Expected Behaviors:\n" + "\n".join(f"- {b}" for b in expected_behaviors),
            f"\n## Input:\n```\n{self._truncate(str(input_data), 500)}\n```",
            f"\n## Output:\n```\n{self._truncate(str(output_data), 500)}\n```\n",
        ]

        if node_config:
            parts.append(f"## Node Configuration:\n{json.dumps(node_config, indent=2)}\n")

        parts.append("\n## Analysis Instructions:")
        parts.append("Analyze why this evaluation failed and provide:")
        parts.append("1. Root cause of the low score")
        parts.append("2. Specific prompt improvements to try")
        parts.append("3. Constraint additions for the prompt")
        parts.append("4. Example outputs that would pass")
        parts.append("5. Risk assessment if left unfixed")

        return "\n".join(parts)

    async def _run_analysis(self, context: str) -> dict[str, Any]:
        """Run LLM-based error analysis."""
        prompt = f"""{context}

Return your analysis as JSON with this exact structure:
{{
  "root_cause": "Specific root cause explanation",
  "suggested_fixes": ["Fix 1", "Fix 2", "Fix 3"],
  "files_to_check": ["file1.py", "file2.py"],
  "debug_steps": ["Step 1", "Step 2", "Step 3"],
  "severity": "critical|high|medium|low",
  "explanation": "Detailed explanation of the analysis"
}}"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        # Extract text from response
        if hasattr(response, "text"):
            text = response.text
        elif hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, "parts"):
                parts = candidate.content.parts
                if parts and hasattr(parts[0], "text"):
                    text = parts[0].text
                else:
                    text = str(response)
            else:
                text = str(response)
        else:
            text = str(response)

        # Parse JSON response
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            analysis = json.loads(text)
        except json.JSONDecodeError:
            # Fallback parsing
            analysis = {
                "root_cause": "Unable to parse analysis",
                "suggested_fixes": ["Review error context manually"],
                "files_to_check": [],
                "debug_steps": ["Check logs"],
                "severity": "medium",
                "explanation": text,
            }

        return analysis

    async def _run_evaluation_analysis(self, context: str) -> dict[str, Any]:
        """Run LLM-based evaluation failure analysis."""
        prompt = f"""{context}

Return your analysis as JSON with this exact structure:
{{
  "root_cause": "Why the evaluation failed",
  "suggested_fixes": ["Fix 1", "Fix 2", "Fix 3"],
  "prompt_improvements": ["Improvement 1", "Improvement 2"],
  "example_good_output": "Example output that would pass evaluation",
  "severity": "critical|high|medium|low",
  "risk_if_unfixed": "What happens if this isn't fixed"
}}"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        # Extract and parse response (same logic as above)
        if hasattr(response, "text"):
            text = response.text
        elif hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, "parts"):
                parts = candidate.content.parts
                if parts and hasattr(parts[0], "text"):
                    text = parts[0].text
                else:
                    text = str(response)
            else:
                text = str(response)
        else:
            text = str(response)

        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            analysis = json.loads(text)
        except json.JSONDecodeError:
            analysis = {
                "root_cause": "Unable to parse analysis",
                "suggested_fixes": [],
                "prompt_improvements": [],
                "severity": "medium",
                "explanation": text,
            }

        return analysis

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... (truncated)"

    def _get_cache_key(self, error: Exception) -> str:
        """Generate cache key for an error."""
        return f"{type(error).__name__}:{str(error)[:100]}"

    def clear_cache(self) -> None:
        """Clear the analysis cache."""
        self._analysis_cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_analyses": len(self._analysis_cache),
        }
