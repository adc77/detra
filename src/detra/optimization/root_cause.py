"""LLM-based root cause analysis for errors and failures."""

import asyncio
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
        unexpected_behaviors: list[str] = None,
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
            unexpected_behaviors: Behaviors that should NOT occur.
            node_config: Node configuration.

        Returns:
            Root cause analysis with suggested prompt improvements.
        """
        unexpected_behaviors = unexpected_behaviors or []
        try:
            # Build evaluation failure context
            context = self._build_evaluation_context(
                node_name=node_name,
                score=score,
                failed_behaviors=failed_behaviors,
                input_data=input_data,
                output_data=output_data,
                expected_behaviors=expected_behaviors,
                unexpected_behaviors=unexpected_behaviors,
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
        import traceback

        parts = [
            "# Exception Root Cause Analysis\n",
            f"## Error Type: `{type(error).__name__}`",
            f"## Error Message: `{str(error)}`\n",
        ]

        if node_name:
            parts.append(f"## Failed in Node: `{node_name}`\n")

        # Add stack trace - this is critical for finding the source
        stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        parts.append(f"## Full Stack Trace:\n```python\n{stack_trace}\n```\n")

        # Extract frame info for better analysis
        if error.__traceback__:
            frames = []
            tb = error.__traceback__
            while tb:
                frame = tb.tb_frame
                frames.append({
                    "file": frame.f_code.co_filename,
                    "line": tb.tb_lineno,
                    "function": frame.f_code.co_name,
                })
                tb = tb.tb_next
            if frames:
                parts.append("## Call Chain (oldest to newest):")
                for i, f in enumerate(frames):
                    marker = "→ " if i == len(frames) - 1 else "  "
                    parts.append(f"{marker}{f['file']}:{f['line']} in `{f['function']}`")
                parts.append("")

        # Add input/output context
        if input_data:
            parts.append(f"## Input Data:\n```\n{self._truncate(str(input_data), 600)}\n```\n")

        if output_data:
            parts.append(f"## Partial Output (before error):\n```\n{self._truncate(str(output_data), 600)}\n```\n")

        # Add additional context
        if context:
            parts.append(f"## Additional Context:\n```json\n{json.dumps(context, indent=2, default=str)}\n```\n")

        return "\n".join(parts)

    def _build_evaluation_context(
        self,
        node_name: str,
        score: float,
        failed_behaviors: list[str],
        input_data: Any,
        output_data: Any,
        expected_behaviors: list[str],
        unexpected_behaviors: list[str],
        node_config: Optional[dict[str, Any]],
    ) -> str:
        """Build context for evaluation failure analysis."""
        parts = [
            "# LLM Output Evaluation Failure - Root Cause Analysis\n",
            f"## Node Function: {node_name}",
            f"## Adherence Score: {score:.2f} (threshold: 0.8)\n",
        ]

        if failed_behaviors:
            parts.append("## FAILED Behavior Checks (output violated these):")
            for b in failed_behaviors:
                parts.append(f"  ❌ {b}")

        if expected_behaviors:
            parts.append("\n## Expected Behaviors (output should have):")
            for b in expected_behaviors:
                parts.append(f"  ✓ {b}")

        if unexpected_behaviors:
            parts.append("\n## Forbidden Behaviors (output must NOT have):")
            for b in unexpected_behaviors:
                parts.append(f"  ✗ {b}")

        parts.append(f"\n## User Input to LLM:\n```\n{self._truncate(str(input_data), 800)}\n```")
        parts.append(f"\n## LLM Output (problematic):\n```\n{self._truncate(str(output_data), 800)}\n```\n")

        if node_config:
            # Only include relevant config fields
            config_summary = {}
            if hasattr(node_config, '__dict__'):
                nc = node_config.__dict__ if hasattr(node_config, '__dict__') else node_config
            else:
                nc = node_config if isinstance(node_config, dict) else {}
            for k in ['description', 'adherence_threshold', 'security_checks']:
                if k in nc:
                    config_summary[k] = nc[k]
            if config_summary:
                parts.append(f"## Node Config:\n{json.dumps(config_summary, indent=2, default=str)}\n")

        return "\n".join(parts)

    async def _run_analysis(self, context: str) -> dict[str, Any]:
        """Run LLM-based error analysis."""
        prompt = f"""{context}

## Your Task: Find the TRUE Root Cause

You are an expert debugger. Analyze the stack trace to find WHERE the error actually originates.

IMPORTANT - Do NOT just look at where the error was CAUGHT. Look for:
1. **Origin File**: The FIRST file in the call chain where bad data/logic was introduced
2. **Propagation Path**: How the error traveled through the codebase
3. **Trigger**: What specific input/state caused this

AVOID generic suggestions like:
- "Add try-catch" (this hides bugs, doesn't fix them)
- "Add validation" (where specifically? what validation?)
- "Check for None" (why is it None in the first place?)

Instead, trace back to find:
- Which function CREATED the bad data?
- Which file has the LOGIC error?
- What ASSUMPTION was violated?

Return JSON:
{{
  "root_cause": "The actual root cause - not where exception was raised, but where the problem originated",
  "origin_file": "file.py:line_number - where the bug actually is",
  "trigger_file": "file.py:line_number - where the error manifested",
  "error_chain": [
    "1. Bad data created in X",
    "2. Passed unchecked to Y",
    "3. Failed when Z tried to use it"
  ],
  "suggested_fixes": [
    "In origin_file:line - change X to Y because...",
    "The real fix is to modify the logic in...",
    "Add validation AT THE SOURCE in..."
  ],
  "files_to_check": ["most_important.py:42", "second.py:100"],
  "debug_steps": [
    "Add breakpoint at origin_file:line",
    "Check value of X when Y happens",
    "Verify assumption Z holds"
  ],
  "severity": "critical|high|medium|low",
  "why_it_happened": "Clear explanation of the logical error",
  "confidence": 0.85
}}"""

        # Run sync Gemini call in executor to not block event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
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

## Your Task: Deep Root Cause Analysis

You are an expert at debugging LLM applications. Analyze WHY the output failed the behavior checks.

CRITICAL: Do NOT suggest generic solutions like:
- "Add try-catch blocks"
- "Add error handling"
- "Validate inputs"
- "Add logging"

Instead, identify the ACTUAL ROOT CAUSE:

1. **Prompt Problem**: Is the prompt missing constraints, unclear, or ambiguous?
2. **Input Problem**: Is the input data malformed, missing fields, or edge case?
3. **Model Limitation**: Is the task too complex or the model hallucinating?
4. **Behavior Mismatch**: Are the expected behaviors unrealistic or conflicting?

For each issue, trace it back to WHERE it originates:
- Which part of the prompt is causing the issue?
- What specific input characteristic triggered this?
- What constraint is missing from the prompt?

Return JSON:
{{
  "root_cause": "Precise explanation of why the LLM produced this output. Be specific - which part of the prompt/input caused this?",
  "root_cause_category": "prompt_unclear|prompt_missing_constraint|input_edge_case|model_hallucination|behavior_unrealistic|context_insufficient",
  "problematic_prompt_section": "Quote the exact part of the prompt (if any) that's causing issues, or null",
  "problematic_input_section": "Quote the exact part of the input (if any) that's causing issues, or null",
  "suggested_fixes": [
    "SPECIFIC fix 1: Add this exact constraint to the prompt: '...'",
    "SPECIFIC fix 2: Modify the prompt to say: '...'",
    "SPECIFIC fix 3: Add this example to few-shot: '...'"
  ],
  "prompt_improvements": [
    "Add explicit constraint: 'You must NOT...'",
    "Add format requirement: 'Return JSON with fields...'",
    "Add grounding instruction: 'Only use information from the document...'"
  ],
  "example_good_output": "Show what the output SHOULD have looked like to pass",
  "severity": "critical|high|medium|low",
  "risk_if_unfixed": "What user-facing problems will occur if not fixed",
  "confidence": 0.85
}}"""

        # Run sync Gemini call in executor to not block event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
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
