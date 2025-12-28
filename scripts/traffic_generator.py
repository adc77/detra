#!/usr/bin/env python3
"""
VertiGuard Traffic Generator - Tests All Features

Generates comprehensive traffic exercising:
1. LLM adherence monitoring
2. Error tracking with root cause analysis
3. Agent workflow monitoring
4. Security scanning (PII, injection)
5. Performance monitoring
6. DSPy optimization triggers

Usage:
    python scripts/traffic_generator.py --requests 50 --delay 2
"""

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
import structlog
import detra
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()


class TrafficGenerator:
    """Comprehensive traffic generator testing all VertiGuard features."""

    def __init__(self, config_path: str, project_id: str, location: str = "us-central1"):
        self.vg = vertiguard.init(config_path)
        aiplatform.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-2.0-flash-exp")

        self.stats = {
            "total": 0,
            "normal_llm": 0,
            "semantic_violation": 0,
            "agent_workflow": 0,
            "pii_exposure": 0,
            "format_violation": 0,
            "error_triggered": 0,
            "high_latency": 0,
            "workflows_completed": 0,
            "errors_captured": 0,
        }

    async def generate_traffic(self, num_requests: int = 50, delay: float = 2.0):
        print(f"\nVertiGuard Traffic Generator")
        print(f"Requests: {num_requests}, Delay: {delay}s")
        print(f"Testing: LLM + Errors + Agents + Security + Performance\n")

        for i in range(num_requests):
            request_type = self._select_request_type()
            print(f"[{i+1}/{num_requests}] {request_type}...", end=" ", flush=True)

            try:
                await self._execute_request(request_type)
                self.stats["total"] += 1
                self.stats[request_type] += 1
                print("OK")
            except Exception as e:
                print(f"ERROR: {str(e)[:50]}")
                self.stats["errors_captured"] += 1

            if i < num_requests - 1:
                await asyncio.sleep(delay)

        self._print_summary()
        return self.stats

    def _select_request_type(self):
        rand = random.random()
        if rand < 0.40: return "normal_llm"
        elif rand < 0.55: return "semantic_violation"
        elif rand < 0.65: return "agent_workflow"
        elif rand < 0.75: return "pii_exposure"
        elif rand < 0.85: return "format_violation"
        elif rand < 0.95: return "error_triggered"
        else: return "high_latency"

    async def _execute_request(self, request_type):
        if request_type == "normal_llm":
            await self._normal_llm()
        elif request_type == "semantic_violation":
            await self._semantic_violation()
        elif request_type == "agent_workflow":
            await self._agent_workflow()
        elif request_type == "pii_exposure":
            await self._pii_exposure()
        elif request_type == "format_violation":
            await self._format_violation()
        elif request_type == "error_triggered":
            await self._error_tracking()
        elif request_type == "high_latency":
            await self._high_latency()

    @detra.trace("extract_entities")
    async def _normal_llm(self):
        contract = self._random_contract()
        prompt = f"Extract entities as JSON from: {contract}\nReturn: {{\"parties\": [], \"dates\": [], \"amounts\": []}}"
        response = await self._call_llm(prompt)
        return self._parse_json(response)

    @detra.trace("extract_entities")
    async def _semantic_violation(self):
        contract = "Agreement between A and B."
        prompt = f"Tell me everything about: {contract}"
        response = await self._call_llm(prompt)
        return self._parse_json(response)

    async def _agent_workflow(self):
        workflow_id = self.vg.agent_monitor.start_workflow("doc_processor")
        self.vg.agent_monitor.track_thought(workflow_id, "Processing contract")
        self.vg.agent_monitor.track_action(workflow_id, "extract", {})

        contract = self._random_contract()
        result = await self._normal_llm.__wrapped__(self, contract)

        self.vg.agent_monitor.track_tool_call(workflow_id, "llm_extract", {}, result, latency_ms=random.uniform(200, 800))
        self.vg.agent_monitor.track_observation(workflow_id, "Complete")
        self.vg.agent_monitor.complete_workflow(workflow_id, result)
        self.stats["workflows_completed"] += 1

    @detra.trace("extract_entities")
    async def _pii_exposure(self):
        pii_doc = "Employee: Jane Smith\nSSN: 123-45-6789\nEmail: jane@company.com"
        prompt = f"Extract all info: {pii_doc}"
        response = await self._call_llm(prompt)
        return self._parse_json(response)

    @detra.trace("extract_entities")
    async def _format_violation(self):
        prompt = "Extract entities from: short text"
        response = await self._call_llm(prompt)
        return {"raw": response, "invalid": True}

    async def _error_tracking(self):
        self.vg.error_tracker.add_breadcrumb("Risky operation", category="test")
        error_funcs = [
            lambda: (_ for _ in ()).throw(ValueError("Invalid format")),
            lambda: {}["missing_key"],
            lambda: "str" + 123,
            lambda: 1 / 0,
        ]
        try:
            random.choice(error_funcs)()
        except Exception as e:
            self.vg.error_tracker.capture_exception(e, context={"test": True}, level="error")

    @detra.trace("extract_entities")
    async def _high_latency(self):
        contract = self._random_contract() * 10
        await asyncio.sleep(random.uniform(2, 4))
        prompt = f"Analyze: {contract}"
        response = await self._call_llm(prompt)
        return self._parse_json(response)

    async def _call_llm(self, prompt: str):
        loop = asyncio.get_event_loop()
        def generate():
            response = self.model.generate_content(prompt)
            return response.text
        return await loop.run_in_executor(None, generate)

    def _parse_json(self, text):
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw": text[:200]}

    def _random_contract(self):
        return random.choice([
            "CONSULTING AGREEMENT\nTechCorp and Partners\nDate: 2024-01-15\nFee: $10,000/month",
            "SERVICE AGREEMENT\nDataTech and Enterprise\nStart: 2024-02-01\nCost: $120,000/year",
            "LICENSE AGREEMENT\nSoftwareCo and Business Ltd\nLicense: $5,000/year\nTerm: 3 years",
        ])

    def _print_summary(self):
        print(f"\nTraffic Generation Complete")
        print(f"Total: {self.stats['total']}")
        print(f"  Normal LLM: {self.stats['normal_llm']}")
        print(f"  Semantic Violations: {self.stats['semantic_violation']}")
        print(f"  Agent Workflows: {self.stats['agent_workflow']} ({self.stats['workflows_completed']} completed)")
        print(f"  PII Exposure: {self.stats['pii_exposure']}")
        print(f"  Format Violations: {self.stats['format_violation']}")
        print(f"  Errors: {self.stats['error_triggered']}")
        print(f"  High Latency: {self.stats['high_latency']}")
        print(f"\nCheck Datadog dashboard for live metrics")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="VertiGuard traffic generator")
    parser.add_argument("--config", default="examples/legal_analyzer/detra.yaml")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--location", default="us-central1")
    args = parser.parse_args()

    generator = TrafficGenerator(args.config, args.project, args.location)
    try:
        await generator.generate_traffic(args.requests, args.delay)
        await generator.vg.close()
    except KeyboardInterrupt:
        print("\nInterrupted")
        await generator.vg.close()


if __name__ == "__main__":
    asyncio.run(main())
