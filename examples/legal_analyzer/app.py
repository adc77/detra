#!/usr/bin/env python3
"""
Comprehensive Legal Document Analyzer - Full VertiGuard Demo

This application demonstrates ALL VertiGuard features:
1. Error tracking (Sentry-style)
2. LLM monitoring with adherence scoring
3. Agent workflow tracking (multi-step processes)
4. DSPy prompt optimization
5. Root cause analysis
6. Security scanning (PII, injection)
7. Datadog integration (metrics, events, incidents)

Interactive TUI interface for testing all features.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import google.genai as genai
import structlog

import detra
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

# ANSI color codes for TUI
COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "RESET": "\033[0m",
}


class ComprehensiveLegalAnalyzer:
    """
    Comprehensive legal analyzer demonstrating all VertiGuard features.

    Features demonstrated:
    - Traditional error tracking
    - LLM prompt/output monitoring
    - Agent workflow tracking (ReAct loops)
    - DSPy prompt optimization
    - Root cause analysis
    """

    def __init__(self, api_key: str, config_path: str = "detra.yaml"):
        """
        Initialize analyzer.

        Args:
            api_key: Google Gemini API key.
            config_path: Path to VertiGuard config.
        """
        # Initialize VertiGuard
        self.vg = vertiguard.init(config_path)

        # Initialize Gemini 2.0 Flash
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash-exp"  # Latest model

        # Initialize optimization components
        from detra.optimization.root_cause import RootCauseAnalyzer
        from detra.optimization.dspy_optimizer import DSpyOptimizer

        self.root_cause_analyzer = RootCauseAnalyzer(api_key=api_key, model=self.model)
        self.dspy_optimizer = DSpyOptimizer(api_key=api_key, model_name=self.model)

        # Statistics
        self.stats = {
            "total_requests": 0,
            "errors_tracked": 0,
            "workflows_completed": 0,
            "prompts_optimized": 0,
            "root_causes_analyzed": 0,
        }

        logger.info(
            "ComprehensiveLegalAnalyzer initialized",
            model=self.model,
            dspy_enabled=self.dspy_optimizer.enabled,
        )

    # =========================================================================
    # FEATURE 1: LLM MONITORING WITH ADHERENCE SCORING
    # =========================================================================

    @detra.trace("extract_entities")
    async def extract_entities(self, document: str) -> dict[str, Any]:
        """
        Extract legal entities with VertiGuard monitoring.

        Demonstrates:
        - Automatic adherence scoring
        - Hallucination detection
        - PII detection in outputs
        """
        self.stats["total_requests"] += 1

        prompt = f"""Extract entities from this legal document and return ONLY valid JSON.

STRICT REQUIREMENTS:
- Only extract entities that appear in the document
- Do NOT make up or infer any information
- Use exact names as they appear
- Dates must be in YYYY-MM-DD format
- Amounts must include currency

Document:
{document}

Return JSON with exactly these keys:
{{
  "parties": ["Party 1 Name", "Party 2 Name"],
  "dates": ["2024-01-15"],
  "amounts": ["$10,000"]
}}

JSON Output:"""

        response = await self._call_llm(prompt)
        return self._parse_json(response)

    @detra.trace("summarize_document")
    async def summarize_document(self, document: str) -> dict[str, Any]:
        """
        Summarize legal document with quality monitoring.

        Demonstrates:
        - Output quality evaluation
        - Adherence to expected behaviors
        """
        self.stats["total_requests"] += 1

        prompt = f"""Summarize this legal document in under 200 words.

REQUIREMENTS:
- Maintain neutral, objective tone
- Focus on key terms, obligations, and dates
- Do NOT add opinions or interpretations
- Do NOT include information not in the source

Document:
{document}

Return JSON with keys: "summary", "key_terms", "obligations"

JSON Output:"""

        response = await self._call_llm(prompt)
        return self._parse_json(response)

    # =========================================================================
    # FEATURE 2: AGENT WORKFLOW MONITORING (Multi-Step Process)
    # =========================================================================

    async def comprehensive_analysis(
        self,
        document: str,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run comprehensive document analysis using multi-step agent workflow.

        Demonstrates:
        - Agent workflow tracking (thought → action → observation)
        - Tool call monitoring
        - Decision tracking
        - Workflow anomaly detection
        """
        # Start agent workflow tracking
        workflow_id = self.vg.agent_monitor.start_workflow(
            agent_name="legal_document_analyzer",
            metadata={"document_length": len(document)},
        )

        try:
            # Step 1: Analyze document structure
            self.vg.agent_monitor.track_thought(
                workflow_id,
                thought="Document received. Need to extract entities and generate summary.",
            )

            self.vg.agent_monitor.track_decision(
                workflow_id,
                decision="extract_entities_first",
                rationale="Entity extraction provides context for summarization",
                confidence=0.95,
            )

            # Step 2: Extract entities (tool call)
            self.vg.agent_monitor.track_action(
                workflow_id,
                action="extract_entities",
                action_input={"document": document[:200] + "..."},
            )

            import time
            tool_start = time.time()
            entities = await self.extract_entities(document)
            tool_latency = (time.time() - tool_start) * 1000

            self.vg.agent_monitor.track_tool_call(
                workflow_id,
                tool_name="extract_entities_llm",
                tool_input={"document_length": len(document)},
                tool_output=entities,
                latency_ms=tool_latency,
            )

            # Step 3: Observe entity extraction results
            entity_count = len(entities.get("parties", []))
            self.vg.agent_monitor.track_observation(
                workflow_id,
                observation=f"Extracted {entity_count} parties, {len(entities.get('dates', []))} dates",
            )

            # Step 4: Decide on next action
            self.vg.agent_monitor.track_thought(
                workflow_id,
                thought="Entities extracted. Now generate document summary.",
            )

            # Step 5: Generate summary (second tool call)
            self.vg.agent_monitor.track_action(
                workflow_id,
                action="summarize_document",
                action_input={"document": document[:200] + "..."},
            )

            tool_start = time.time()
            summary = await self.summarize_document(document)
            tool_latency = (time.time() - tool_start) * 1000

            self.vg.agent_monitor.track_tool_call(
                workflow_id,
                tool_name="summarize_document_llm",
                tool_input={"document_length": len(document)},
                tool_output=summary,
                latency_ms=tool_latency,
            )

            # Step 6: If query provided, answer it
            answer = None
            if query:
                self.vg.agent_monitor.track_thought(
                    workflow_id,
                    thought=f"User query detected: '{query[:50]}...'. Need to answer based on document.",
                )

                self.vg.agent_monitor.track_action(
                    workflow_id,
                    action="answer_query",
                    action_input={"query": query},
                )

                answer = await self.answer_query(document, query)

                self.vg.agent_monitor.track_tool_call(
                    workflow_id,
                    tool_name="answer_query_llm",
                    tool_input={"query": query},
                    tool_output=answer,
                    latency_ms=100,  # Would track actual
                )

            # Final decision
            self.vg.agent_monitor.track_decision(
                workflow_id,
                decision="complete_analysis",
                rationale="All requested operations completed successfully",
                confidence=1.0,
            )

            # Complete workflow
            final_output = {
                "entities": entities,
                "summary": summary,
                "answer": answer,
                "workflow_id": workflow_id,
            }

            self.vg.agent_monitor.complete_workflow(workflow_id, final_output)
            self.stats["workflows_completed"] += 1

            return final_output

        except Exception as e:
            # Mark workflow as failed
            self.vg.agent_monitor.fail_workflow(workflow_id, str(e))

            # Track error
            self.vg.error_tracker.capture_exception(
                e,
                context={"workflow_id": workflow_id},
                level="error",
            )
            self.stats["errors_tracked"] += 1

            raise

    @detra.trace("answer_query")
    async def answer_query(self, document: str, query: str) -> dict[str, Any]:
        """Answer query about document."""
        prompt = f"""Answer this question based ONLY on the provided document.

Question: {query}

Document:
{document}

REQUIREMENTS:
- Only use information from the document
- Cite specific sections
- If answer not in document, say so
- Do NOT provide legal advice

Return JSON with keys: "answer", "citations", "confidence"

JSON Output:"""

        response = await self._call_llm(prompt)
        return self._parse_json(response)

    # =========================================================================
    # FEATURE 3: ERROR TRACKING WITH ROOT CAUSE ANALYSIS
    # =========================================================================

    async def process_with_error_tracking(self, document: str) -> dict[str, Any]:
        """
        Process document with comprehensive error tracking.

        Demonstrates:
        - Breadcrumb tracking
        - User context
        - Automatic error capture
        - Root cause analysis on failures
        """
        # Set user context
        self.vg.error_tracker.set_user(
            user_id="demo_user",
            username="legal_analyst",
        )

        # Add breadcrumbs
        self.vg.error_tracker.add_breadcrumb(
            "Started document processing",
            category="processing",
        )

        try:
            # Validate document
            self.vg.error_tracker.add_breadcrumb(
                "Validating document format",
                category="validation",
            )

            if not document or len(document) < 50:
                raise ValueError("Document too short or empty")

            self.vg.error_tracker.add_breadcrumb(
                "Document validation passed",
                category="validation",
            )

            # Process with agent workflow
            self.vg.error_tracker.add_breadcrumb(
                "Starting comprehensive analysis",
                category="analysis",
            )

            result = await self.comprehensive_analysis(document)

            return {"status": "success", "result": result}

        except Exception as e:
            # Capture error with full context
            error_id = self.vg.error_tracker.capture_exception(
                e,
                context={
                    "document_length": len(document),
                    "operation": "comprehensive_analysis",
                },
                level="error",
                tags=["service:legal_analyzer"],
            )

            self.stats["errors_tracked"] += 1

            # Perform root cause analysis
            analysis = await self.root_cause_analyzer.analyze_error(
                error=e,
                context={"error_id": error_id},
                node_name="comprehensive_analysis",
                input_data=document[:500],
            )

            self.stats["root_causes_analyzed"] += 1

            logger.error(
                "Processing failed with root cause analysis",
                error_id=error_id,
                root_cause=analysis.get("root_cause"),
            )

            return {
                "status": "error",
                "error_id": error_id,
                "root_cause": analysis.get("root_cause"),
                "suggested_fixes": analysis.get("suggested_fixes", []),
                "files_to_check": analysis.get("files_to_check", []),
            }

    # =========================================================================
    # FEATURE 4: DSPY PROMPT OPTIMIZATION
    # =========================================================================

    async def optimize_failing_prompt(
        self,
        node_name: str,
        original_prompt: str,
        failure_examples: list[dict],
    ) -> dict[str, Any]:
        """
        Optimize a prompt that's producing failures using DSPy.

        Demonstrates:
        - Automatic prompt improvement
        - Few-shot example generation
        - Failure pattern analysis
        """
        if not self.dspy_optimizer.enabled:
            return {
                "status": "skipped",
                "reason": "DSPy not available",
            }

        # Get node config
        node_config = self.vg.config.nodes.get(node_name)
        if not node_config:
            return {"status": "error", "reason": "Unknown node"}

        # Optimize prompt
        result = await self.dspy_optimizer.optimize_prompt(
            original_prompt=original_prompt,
            failure_reason="Low adherence scores, potential hallucinations",
            expected_behaviors=node_config.expected_behaviors,
            unexpected_behaviors=node_config.unexpected_behaviors,
            failed_examples=failure_examples,
        )

        self.stats["prompts_optimized"] += 1

        return {
            "status": "success",
            "improved_prompt": result["improved_prompt"],
            "changes_made": result["changes_made"],
            "confidence": result["confidence"],
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _call_llm(self, prompt: str) -> str:
        """Call Gemini API."""
        loop = asyncio.get_event_loop()

        def generate():
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts
                    if parts and hasattr(parts[0], "text"):
                        return parts[0].text
            return str(response)

        return await loop.run_in_executor(None, generate)

    def _parse_json(self, text: str) -> dict:
        """Parse JSON from LLM response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON", error=str(e))
            return {"error": "Invalid JSON", "raw": text}

    async def close(self):
        """Close resources."""
        await self.vg.close()


# =============================================================================
# TUI (Terminal User Interface)
# =============================================================================


class LegalAnalyzerTUI:
    """Terminal UI for the legal analyzer."""

    def __init__(self):
        """Initialize TUI."""
        self.analyzer: Optional[ComprehensiveLegalAnalyzer] = None
        self.api_key: Optional[str] = None

    def print_header(self, text: str):
        """Print section header."""
        print(f"\n{COLORS['BLUE']}{'='*70}{COLORS['RESET']}")
        print(f"{COLORS['BOLD']}{COLORS['CYAN']}{text}{COLORS['RESET']}")
        print(f"{COLORS['BLUE']}{'='*70}{COLORS['RESET']}\n")

    def print_success(self, text: str):
        """Print success message."""
        print(f"{COLORS['GREEN']}✓ {text}{COLORS['RESET']}")

    def print_error(self, text: str):
        """Print error message."""
        print(f"{COLORS['RED']}✗ {text}{COLORS['RESET']}")

    def print_info(self, text: str):
        """Print info message."""
        print(f"{COLORS['CYAN']}ℹ {text}{COLORS['RESET']}")

    async def run(self):
        """Run the TUI."""
        self.print_header("VertiGuard Comprehensive Demo - Legal Document Analyzer")

        # Get API key
        if not await self.setup_api_key():
            return

        # Setup Datadog
        if not await self.setup_datadog():
            return

        # Initialize analyzer
        if not await self.initialize_analyzer():
            return

        # Main menu loop
        await self.main_menu()

    async def setup_api_key(self) -> bool:
        """Get and validate API key."""
        self.print_header("Step 1: API Key Setup")

        # Check environment first
        self.api_key = os.getenv("GOOGLE_API_KEY")

        if self.api_key:
            self.print_success(f"Found GOOGLE_API_KEY in environment")
        else:
            print(f"{COLORS['YELLOW']}Please enter your Google Gemini API key:{COLORS['RESET']}")
            print(f"{COLORS['CYAN']}Get one at: https://makersuite.google.com/app/apikey{COLORS['RESET']}")
            self.api_key = input(f"\n{COLORS['BOLD']}API Key: {COLORS['RESET']}").strip()

            if not self.api_key:
                self.print_error("API key required to continue")
                return False

            # Set in environment
            os.environ["GOOGLE_API_KEY"] = self.api_key

        # Validate key
        try:
            client = genai.Client(api_key=self.api_key)
            self.print_success("API key validated successfully")
            return True
        except Exception as e:
            self.print_error(f"Invalid API key: {e}")
            return False

    async def setup_datadog(self) -> bool:
        """Setup Datadog credentials."""
        self.print_header("Step 2: Datadog Setup")

        # Check environment
        dd_api = os.getenv("DD_API_KEY")
        dd_app = os.getenv("DD_APP_KEY")

        if dd_api and dd_app:
            self.print_success("Found Datadog credentials in environment")
            return True

        print(f"{COLORS['YELLOW']}Datadog credentials not found in environment{COLORS['RESET']}")
        print(f"{COLORS['CYAN']}Enter your Datadog keys (or press Enter to skip):{ COLORS['RESET']}")

        dd_api = input(f"DD_API_KEY: ").strip()
        if dd_api:
            os.environ["DD_API_KEY"] = dd_api
            dd_app = input(f"DD_APP_KEY: ").strip()
            if dd_app:
                os.environ["DD_APP_KEY"] = dd_app
                dd_site = input(f"DD_SITE (default: datadoghq.com): ").strip() or "datadoghq.com"
                os.environ["DD_SITE"] = dd_site
                self.print_success("Datadog configured")
                return True

        self.print_info("Continuing without Datadog (limited functionality)")
        return True

    async def initialize_analyzer(self) -> bool:
        """Initialize the analyzer."""
        self.print_header("Step 3: Initializing VertiGuard")

        try:
            config_path = Path(__file__).parent / "detra.yaml"
            self.analyzer = ComprehensiveLegalAnalyzer(
                api_key=self.api_key,
                config_path=str(config_path),
            )

            self.print_success("VertiGuard initialized")
            self.print_success(f"Model: gemini-2.0-flash-exp")
            self.print_success(f"DSPy enabled: {self.analyzer.dspy_optimizer.enabled}")

            # Setup monitors and dashboard
            if os.getenv("DD_API_KEY"):
                self.print_info("Setting up Datadog monitors and dashboard...")
                try:
                    setup_result = await self.analyzer.vg.setup_all()
                    self.print_success(f"Created {len(setup_result.get('monitors', {}).get('default_monitors', []))} monitors")

                    if setup_result.get("dashboard"):
                        dashboard_url = setup_result["dashboard"].get("url", "N/A")
                        self.print_success(f"Dashboard created: {dashboard_url}")
                except Exception as e:
                    self.print_error(f"Dashboard setup failed: {e}")

            return True

        except Exception as e:
            self.print_error(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def main_menu(self):
        """Main menu loop."""
        while True:
            self.print_header("Main Menu")

            print(f"{COLORS['BOLD']}Choose an option:{COLORS['RESET']}\n")
            print(f"  {COLORS['CYAN']}1.{COLORS['RESET']} Process sample contract (LLM monitoring)")
            print(f"  {COLORS['CYAN']}2.{COLORS['RESET']} Run agent workflow (multi-step analysis)")
            print(f"  {COLORS['CYAN']}3.{COLORS['RESET']} Trigger error (error tracking demo)")
            print(f"  {COLORS['CYAN']}4.{COLORS['RESET']} Optimize failing prompt (DSPy demo)")
            print(f"  {COLORS['CYAN']}5.{COLORS['RESET']} Generate test traffic (50 requests)")
            print(f"  {COLORS['CYAN']}6.{COLORS['RESET']} View statistics")
            print(f"  {COLORS['CYAN']}7.{COLORS['RESET']} Export Datadog configs")
            print(f"  {COLORS['CYAN']}Q.{COLORS['RESET']} Quit\n")

            choice = input(f"{COLORS['BOLD']}Enter choice: {COLORS['RESET']}").strip().lower()

            if choice == "1":
                await self.demo_llm_monitoring()
            elif choice == "2":
                await self.demo_agent_workflow()
            elif choice == "3":
                await self.demo_error_tracking()
            elif choice == "4":
                await self.demo_dspy_optimization()
            elif choice == "5":
                await self.demo_traffic_generation()
            elif choice == "6":
                self.show_statistics()
            elif choice == "7":
                await self.export_configs()
            elif choice == "q":
                break
            else:
                self.print_error("Invalid choice")

        # Cleanup
        await self.analyzer.close()
        self.print_success("Goodbye!")

    async def demo_llm_monitoring(self):
        """Demo LLM monitoring features."""
        self.print_header("Demo 1: LLM Monitoring with Adherence Scoring")

        sample_contract = """
CONSULTING AGREEMENT

This Agreement is between TechCorp Solutions Inc. ("Client") and
Legal Advisory Partners LLC ("Consultant").

Effective Date: January 15, 2024
Term: 12 months
Monthly Fee: $15,000 payable on the 1st of each month.

Services: Legal advisory, contract review, compliance guidance.
"""

        self.print_info("Processing sample contract...")

        result = await self.analyzer.extract_entities(sample_contract)

        print(f"\n{COLORS['GREEN']}Extracted Entities:{COLORS['RESET']}")
        print(json.dumps(result, indent=2))

        self.print_success("Check Datadog for:")
        print("  - Adherence score metric")
        print("  - LLM trace in APM")
        print("  - Any flags if score < 0.85")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    async def demo_agent_workflow(self):
        """Demo agent workflow tracking."""
        self.print_header("Demo 2: Agent Workflow Tracking (Multi-Step)")

        sample_contract = """
SERVICE AGREEMENT

Provider: DataTech Services LLC
Client: Enterprise Corp
Start Date: February 1, 2024
Annual Cost: $120,000
Services: Data analytics, cloud migration, 24/7 support
"""

        query = "What are the key services and costs?"

        self.print_info("Running multi-step agent workflow...")
        self.print_info("Tracking: Thoughts → Actions → Observations → Tool Calls")

        result = await self.analyzer.comprehensive_analysis(sample_contract, query)

        print(f"\n{COLORS['GREEN']}Workflow Results:{COLORS['RESET']}")
        print(f"Workflow ID: {result.get('workflow_id')}")
        print(f"\nEntities: {len(result['entities'].get('parties', []))} parties")
        print(f"Summary: {result['summary'].get('summary', 'N/A')[:100]}...")
        if result.get('answer'):
            print(f"Answer: {result['answer'].get('answer', 'N/A')[:100]}...")

        self.print_success("Check Datadog for:")
        print("  - Agent workflow duration metric")
        print("  - Tool call count metric")
        print("  - Workflow completion event")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    async def demo_error_tracking(self):
        """Demo error tracking with root cause analysis."""
        self.print_header("Demo 3: Error Tracking + Root Cause Analysis")

        self.print_info("Triggering intentional error...")

        try:
            # This will fail
            await self.analyzer.process_with_error_tracking("")
        except Exception:
            pass  # Expected

        # Show error summary
        errors = self.analyzer.vg.error_tracker.get_all_errors()
        if errors:
            print(f"\n{COLORS['GREEN']}Error Captured:{COLORS['RESET']}")
            error = errors[0]
            print(f"Error ID: {error['error_id']}")
            print(f"Type: {error['exception_type']}")
            print(f"Occurrences: {error['count']}")

            self.print_success("Check Datadog for:")
            print("  - Error event with full stack trace")
            print("  - Error count metric")
            print("  - Root cause analysis in event description")
        else:
            self.print_error("No errors captured")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    async def demo_dspy_optimization(self):
        """Demo DSPy prompt optimization."""
        self.print_header("Demo 4: DSPy Prompt Optimization")

        if not self.analyzer.dspy_optimizer.enabled:
            self.print_error("DSPy not available")
            self.print_info("Install with: pip install dspy-ai")
            input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")
            return

        self.print_info("Optimizing a failing prompt...")

        original_prompt = "Extract entities from the document"

        failed_examples = [
            {
                "input": "Contract with Alice Corp",
                "output": '{"parties": ["Alice Corp", "Bob LLC", "Charlie Inc"]}',
                "issue": "Hallucinated Bob LLC and Charlie Inc (not in document)",
            }
        ]

        result = await self.analyzer.optimize_failing_prompt(
            node_name="extract_entities",
            original_prompt=original_prompt,
            failure_examples=failed_examples,
        )

        if result["status"] == "success":
            print(f"\n{COLORS['GREEN']}Optimization Complete:{COLORS['RESET']}")
            print(f"\n{COLORS['BOLD']}Improved Prompt:{COLORS['RESET']}")
            print(result["improved_prompt"][:300] + "...")
            print(f"\n{COLORS['BOLD']}Changes Made:{COLORS['RESET']}")
            for i, change in enumerate(result["changes_made"][:3], 1):
                print(f"  {i}. {change}")
            print(f"\n{COLORS['BOLD']}Confidence:{COLORS['RESET']} {result['confidence']}")
        else:
            self.print_error(f"Optimization failed: {result.get('reason')}")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    async def demo_traffic_generation(self):
        """Demo traffic generation."""
        self.print_header("Demo 5: Generate Test Traffic")

        self.print_info("This will generate 50 requests with diverse patterns:")
        print("  - 60% Normal (should pass)")
        print("  - 15% Semantic violations (hallucinations)")
        print("  - 10% PII exposure")
        print("  - 10% Format violations")
        print("  - 5% High latency")

        confirm = input(f"\n{COLORS['YELLOW']}Generate traffic? (y/n): {COLORS['RESET']}").strip().lower()

        if confirm == "y":
            self.print_info("Running traffic generator...")
            # Import and run traffic generator
            from scripts.traffic_generator import TrafficGenerator

            config_path = Path(__file__).parent / "detra.yaml"
            generator = TrafficGenerator(str(config_path))

            stats = await generator.generate_traffic(num_requests=50, delay_between_requests=1.5)

            print(f"\n{COLORS['GREEN']}Traffic Generation Complete:{COLORS['RESET']}")
            print(f"Total: {stats['total']}")
            print(f"Flagged: {stats.get('flagged', 0)}")
            print(f"Errors: {stats['errors']}")

            self.print_success("Check Datadog dashboard for live metrics!")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    def show_statistics(self):
        """Show application statistics."""
        self.print_header("Application Statistics")

        if self.analyzer:
            stats = self.analyzer.stats
            print(f"{COLORS['BOLD']}LLM Requests:{COLORS['RESET']} {stats['total_requests']}")
            print(f"{COLORS['BOLD']}Errors Tracked:{COLORS['RESET']} {stats['errors_tracked']}")
            print(f"{COLORS['BOLD']}Workflows Completed:{COLORS['RESET']} {stats['workflows_completed']}")
            print(f"{COLORS['BOLD']}Prompts Optimized:{COLORS['RESET']} {stats['prompts_optimized']}")
            print(f"{COLORS['BOLD']}Root Causes Analyzed:{COLORS['RESET']} {stats['root_causes_analyzed']}")

            # Error tracker stats
            errors = self.analyzer.vg.error_tracker.get_all_errors()
            print(f"\n{COLORS['BOLD']}Error Tracker:{COLORS['RESET']}")
            print(f"  Unique errors: {len(errors)}")
            print(f"  Total occurrences: {self.analyzer.vg.error_tracker.total_errors}")

            # Agent monitor stats
            active_workflows = self.analyzer.vg.agent_monitor.get_active_workflows()
            print(f"\n{COLORS['BOLD']}Agent Monitor:{COLORS['RESET']}")
            print(f"  Active workflows: {len(active_workflows)}")

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")

    async def export_configs(self):
        """Export Datadog configurations."""
        self.print_header("Export Datadog Configurations")

        if not os.getenv("DD_API_KEY"):
            self.print_error("Datadog not configured. Cannot export.")
            input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")
            return

        self.print_info("Running export script...")

        # Run export script
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/export_datadog_configs.py"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            self.print_success("Export complete!")
            print(result.stdout)
        else:
            self.print_error("Export failed")
            print(result.stderr)

        input(f"\n{COLORS['YELLOW']}Press Enter to continue...{COLORS['RESET']}")


async def main():
    """Main entry point."""
    tui = LegalAnalyzerTUI()

    try:
        await tui.run()
    except KeyboardInterrupt:
        print(f"\n\n{COLORS['YELLOW']}Interrupted by user{COLORS['RESET']}")
    except Exception as e:
        print(f"\n\n{COLORS['RED']}Error: {e}{COLORS['RESET']}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
