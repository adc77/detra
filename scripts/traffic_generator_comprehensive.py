#!/usr/bin/env python3
"""
Traffic Generator for detra

Generates comprehensive traffic that exercises ALL detra features:
1. Normal LLM calls (adherence monitoring)
2. Errors (error tracking)
3. Agent workflows (workflow monitoring)
4. Semantic violations (hallucinations)
5. PII exposure (security scanning)
6. Format violations
7. High latency scenarios

Run: python scripts/traffic_generator_comprehensive.py
"""

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import google.genai as genai
import structlog

import detra
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()


class ComprehensiveTrafficGenerator:
    """
    Generates comprehensive traffic to test all detra features.

    Traffic Distribution:
    - 40% Normal LLM calls
    - 15% Semantic violations
    - 10% With agent workflows
    - 10% PII exposure
    - 10% Format violations
    - 10% Errors/exceptions
    - 5% High latency
    """

    def __init__(self, config_path: str, api_key: str):
        """Initialize generator."""
        self.vg = detra.init(config_path)
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

        self.stats = {
            "total": 0,
            "normal_llm": 0,
            "semantic_violation": 0,
            "agent_workflow": 0,
            "pii_exposure": 0,
            "format_violation": 0,
            "error_triggered": 0,
            "high_latency": 0,
            "flagged": 0,
            "errors": 0,
            "workflows_completed": 0,
        }

    async def generate_traffic(
        self,
        num_requests: int = 100,
        delay_between_requests: float = 2.0,
    ) -> dict:
        """Generate comprehensive traffic."""
        print(f"\n{'='*70}")
        print(f"COMPREHENSIVE TRAFFIC GENERATION")
        print(f"{'='*70}")
        print(f"Total requests: {num_requests}")
        print(f"Delay: {delay_between_requests}s")
        print(f"Testing: LLM monitoring, Errors, Agents, Security, Performance")
        print(f"{'='*70}\n")

        for i in range(num_requests):
            request_type = self._select_request_type()
            print(f"[{i+1}/{num_requests}] {request_type}...", end=" ")

            try:
                await self._execute_request(request_type)
                self.stats["total"] += 1
                self.stats[request_type] += 1
                print("✓")
            except Exception as e:
                print(f"✗ {str(e)[:50]}")
                self.stats["errors"] += 1

            if i < num_requests - 1:
                await asyncio.sleep(delay_between_requests)

        self._print_summary()
        return self.stats

    def _select_request_type(self) -> str:
        """Select request type based on probability."""
        rand = random.random()

        if rand < 0.40:
            return "normal_llm"
        elif rand < 0.55:
            return "semantic_violation"
        elif rand < 0.65:
            return "agent_workflow"
        elif rand < 0.75:
            return "pii_exposure"
        elif rand < 0.85:
            return "format_violation"
        elif rand < 0.95:
            return "error_triggered"
        else:
            return "high_latency"

    async def _execute_request(self, request_type: str):
        """Execute request based on type."""
        if request_type == "normal_llm":
            await self._test_normal_llm()
        elif request_type == "semantic_violation":
            await self._test_semantic_violation()
        elif request_type == "agent_workflow":
            await self._test_agent_workflow()
        elif request_type == "pii_exposure":
            await self._test_pii_exposure()
        elif request_type == "format_violation":
            await self._test_format_violation()
        elif request_type == "error_triggered":
            await self._test_error_tracking()
        elif request_type == "high_latency":
            await self._test_high_latency()

    # =========================================================================
    # TEST 1: Normal LLM Monitoring
    # =========================================================================

    @detra.trace("extract_entities")
    async def _test_normal_llm(self):
        """Test normal LLM call with adherence monitoring."""
        contract = self._get_random_contract()

        prompt = f"""Extract entities as JSON:

{contract}

Return: {{"parties": [...], "dates": [...], "amounts": [...]}}"""

        response = await self._call_llm(prompt)
        return self._parse_json(response)

    # =========================================================================
    # TEST 2: Semantic Violations (Hallucinations)
    # =========================================================================

    @detra.trace("extract_entities")
    async def _test_semantic_violation(self):
        """Test with vague prompt that encourages hallucinations."""
        contract = "Agreement between A and B for consulting services."

        # Vague prompt that encourages making up information
        prompt = f"Tell me everything about the parties, dates, and amounts in: {contract}"

        response = await self._call_llm(prompt)
        # This should get flagged for low adherence
        return self._parse_json(response)

    # =========================================================================
    # TEST 3: Agent Workflow Monitoring
    # =========================================================================

    async def _test_agent_workflow(self):
        """Test multi-step agent workflow."""
        # Start workflow
        workflow_id = self.vg.agent_monitor.start_workflow(
            "document_processor",
            metadata={"test": True},
        )

        # Track steps
        self.vg.agent_monitor.track_thought(workflow_id, "Processing contract")
        self.vg.agent_monitor.track_action(workflow_id, "extract", {})

        # Make LLM call
        contract = self._get_random_contract()
        result = await self._test_normal_llm.__wrapped__(self, contract)

        self.vg.agent_monitor.track_tool_call(
            workflow_id,
            "llm_extract",
            {},
            result,
            latency_ms=random.uniform(200, 800),
        )

        self.vg.agent_monitor.track_observation(workflow_id, "Extraction complete")
        self.vg.agent_monitor.complete_workflow(workflow_id, result)

        self.stats["workflows_completed"] += 1

    # =========================================================================
    # TEST 4: PII Exposure
    # =========================================================================

    @detra.trace("extract_entities")
    async def _test_pii_exposure(self):
        """Test with document containing PII."""
        pii_contract = """
Employment Agreement

Employee: Jane Smith
SSN: 123-45-6789
Email: jane.smith@company.com
Phone: (555) 987-6543

Salary: $150,000/year
"""

        prompt = f"Extract all information: {pii_contract}"
        response = await self._call_llm(prompt)

        # This should trigger PII detection
        return self._parse_json(response)

    # =========================================================================
    # TEST 5: Format Violations
    # =========================================================================

    @detra.trace("extract_entities")
    async def _test_format_violation(self):
        """Test that produces invalid format."""
        prompt = "Extract entities from: Brief contract text"

        response = await self._call_llm(prompt)

        # Return malformed response
        return {"raw": response, "invalid_format": True}

    # =========================================================================
    # TEST 6: Error Tracking
    # =========================================================================

    async def _test_error_tracking(self):
        """Test error tracking and root cause analysis."""
        # Add breadcrumb
        self.vg.error_tracker.add_breadcrumb(
            "Starting risky operation",
            category="test",
        )

        # Trigger random error
        error_types = [
            ("ValueError", lambda: (_ for _ in ()).throw(ValueError("Invalid input format"))),
            ("KeyError", lambda: {}["nonexistent_key"]),
            ("TypeError", lambda: "string" + 123),
            ("ZeroDivisionError", lambda: 1 / 0),
        ]

        error_name, error_func = random.choice(error_types)

        try:
            error_func()
        except Exception as e:
            # Capture with context
            error_id = self.vg.error_tracker.capture_exception(
                e,
                context={"test_type": "error_tracking"},
                level="error",
            )
            # Don't re-raise, this is intentional

    # =========================================================================
    # TEST 7: High Latency
    # =========================================================================

    @detra.trace("extract_entities")
    async def _test_high_latency(self):
        """Test high latency scenario."""
        # Create complex document
        contract = self._get_random_contract() * 10  # Make it large

        # Add artificial delay
        await asyncio.sleep(random.uniform(2, 4))

        prompt = f"Thoroughly analyze: {contract}"
        response = await self._call_llm(prompt)

        return self._parse_json(response)

    # =========================================================================
    # HELPERS
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
        """Parse JSON response."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw": text[:200]}

    def _get_random_contract(self) -> str:
        """Get random contract text."""
        contracts = [
            """CONSULTING AGREEMENT
TechCorp Solutions Inc. and Advisory Partners LLC
Date: January 15, 2024
Fee: $10,000/month""",

            """SERVICE AGREEMENT
DataTech Services and Enterprise Corp
Start: February 1, 2024
Cost: $120,000/year""",

            """LICENSING AGREEMENT
SoftwareCo Inc. and Business Solutions Ltd
License: $5,000/year
Term: 3 years from March 1, 2024""",
        ]
        return random.choice(contracts)

    def _print_summary(self):
        """Print traffic generation summary."""
        print(f"\n{'='*70}")
        print(f"TRAFFIC GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Total: {self.stats['total']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"\nBreakdown:")
        print(f"  Normal LLM:          {self.stats['normal_llm']:3d}")
        print(f"  Semantic Violations: {self.stats['semantic_violation']:3d}")
        print(f"  Agent Workflows:     {self.stats['agent_workflow']:3d} ({self.stats['workflows_completed']} completed)")
        print(f"  PII Exposure:        {self.stats['pii_exposure']:3d}")
        print(f"  Format Violations:   {self.stats['format_violation']:3d}")
        print(f"  Errors Triggered:    {self.stats['error_triggered']:3d}")
        print(f"  High Latency:        {self.stats['high_latency']:3d}")
        print(f"{'='*70}\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="examples/legal_analyzer/detra.yaml")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--delay", type=float, default=2.0)

    args = parser.parse_args()

    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set")
        print("Export it or it will be prompted")
        sys.exit(1)

    generator = ComprehensiveTrafficGenerator(args.config, api_key)

    try:
        await generator.generate_traffic(args.requests, args.delay)
        await generator.vg.close()
    except KeyboardInterrupt:
        print("\nInterrupted")
        await generator.vg.close()


if __name__ == "__main__":
    asyncio.run(main())
