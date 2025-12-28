#!/usr/bin/env python3
"""
End-to-End Test Script for VertiGuard

Tests all major functionality:
1. VertiGuard initialization
2. Decorator tracing
3. Evaluation engine
4. Datadog integration
5. Monitor and dashboard creation

Run: python scripts/test_e2e.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

import detra
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()


class E2ETestSuite:
    """End-to-end test suite for VertiGuard."""

    def __init__(self, config_path: str):
        """Initialize test suite."""
        self.config_path = config_path
        self.vg = None
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("VERTIGUARD END-TO-END TEST SUITE")
        print("="*60 + "\n")

        tests = [
            ("Initialization", self.test_initialization),
            ("Configuration Loading", self.test_configuration),
            ("Decorator Tracing", self.test_decorator),
            ("Manual Evaluation", self.test_manual_evaluation),
            ("Datadog Metrics", self.test_datadog_metrics),
            ("Monitor Creation", self.test_monitor_creation),
            ("Dashboard Creation", self.test_dashboard_creation),
            ("Incident Management", self.test_incident_management),
            ("Root Cause Analysis", self.test_root_cause_analysis),
        ]

        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)

        # Print results
        self.print_results()

        # Cleanup
        if self.vg:
            await self.vg.close()

        # Exit with appropriate code
        sys.exit(0 if self.failed == 0 else 1)

    async def run_test(self, name: str, test_func):
        """Run a single test."""
        print(f"Testing: {name}...", end=" ")
        try:
            await test_func()
            print("✓ PASS")
            self.passed += 1
        except AssertionError as e:
            print(f"✗ FAIL")
            self.failed += 1
            self.errors.append((name, str(e)))
        except Exception as e:
            print(f"✗ ERROR")
            self.failed += 1
            self.errors.append((name, f"Unexpected error: {str(e)}"))

    async def test_initialization(self):
        """Test VertiGuard initialization."""
        self.vg = vertiguard.init(self.config_path)
        assert self.vg is not None, "Failed to initialize VertiGuard"
        assert vertiguard.is_initialized(), "VertiGuard not marked as initialized"

    async def test_configuration(self):
        """Test configuration loading."""
        assert self.vg.config is not None, "Config not loaded"
        assert self.vg.config.app_name, "App name not set"
        assert self.vg.config.datadog, "Datadog config not loaded"
        assert self.vg.config.nodes, "No nodes configured"

    async def test_decorator(self):
        """Test decorator functionality."""

        @self.vg.trace("test_node")
        async def test_function(input_text: str) -> str:
            return f"Processed: {input_text}"

        result = await test_function("test input")
        assert result == "Processed: test input", "Decorator altered output"

    async def test_manual_evaluation(self):
        """Test manual evaluation."""
        # Get a configured node
        node_name = list(self.vg.config.nodes.keys())[0]

        result = await self.vg.evaluate(
            node_name=node_name,
            input_data="Test input",
            output_data="Test output",
        )

        assert result is not None, "Evaluation returned None"
        assert hasattr(result, 'score'), "Evaluation result missing score"
        assert 0 <= result.score <= 1, f"Invalid score: {result.score}"

    async def test_datadog_metrics(self):
        """Test Datadog metrics submission."""
        import time

        metrics = [
            {
                "metric": "vertiguard.test.metric",
                "type": "gauge",
                "points": [[int(time.time()), 1.0]],
                "tags": ["test:e2e"],
            }
        ]

        success = await self.vg.datadog_client.submit_metrics(metrics)
        assert success, "Failed to submit metrics to Datadog"

    async def test_monitor_creation(self):
        """Test monitor creation."""
        # Create a test monitor
        result = await self.vg.monitor_manager.create_monitor(
            monitor_key="adherence_warning",
            slack_channel="test-alerts",
        )

        assert result is not None, "Failed to create monitor"
        assert "id" in result, "Monitor missing ID"

    async def test_dashboard_creation(self):
        """Test dashboard creation."""
        dashboard_result = await self.vg.setup_dashboard()

        assert dashboard_result is not None, "Failed to create dashboard"
        assert "title" in dashboard_result, "Dashboard missing title"

    async def test_incident_management(self):
        """Test incident creation."""
        incident = await self.vg.incident_manager.create_manual_incident(
            title="Test Incident - E2E",
            description="This is a test incident from E2E tests",
            severity="SEV-4",
        )

        assert incident is not None, "Failed to create incident"
        assert "id" in incident, "Incident missing ID"

    async def test_root_cause_analysis(self):
        """Test root cause analyzer."""
        from detra.optimization.root_cause import RootCauseAnalyzer

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print(" (SKIP - no API key)")
            return

        analyzer = RootCauseAnalyzer(api_key=api_key)

        # Create a test error
        try:
            raise ValueError("Test error for analysis")
        except ValueError as e:
            analysis = await analyzer.analyze_error(
                error=e,
                context={"test": True},
            )

            assert "root_cause" in analysis, "Analysis missing root_cause"
            assert "suggested_fixes" in analysis, "Analysis missing fixes"

    def print_results(self):
        """Print test results."""
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        print(f"\nPassed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total:  {self.passed + self.failed}")

        if self.errors:
            print("\n" + "="*60)
            print("FAILURES")
            print("="*60)
            for test_name, error in self.errors:
                print(f"\n{test_name}:")
                print(f"  {error}")

        print("\n" + "="*60)

        if self.failed == 0:
            print("✅ ALL TESTS PASSED")
        else:
            print(f"❌ {self.failed} TEST(S) FAILED")

        print("="*60 + "\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run VertiGuard E2E tests")
    parser.add_argument(
        "--config",
        default="examples/legal_analyzer/detra.yaml",
        help="Path to detra.yaml config",
    )

    args = parser.parse_args()

    # Check environment variables
    required_vars = ["DD_API_KEY", "DD_APP_KEY", "GOOGLE_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("\nSet them with:")
        for var in missing:
            print(f"  export {var}=your_key_here")
        sys.exit(1)

    # Run tests
    suite = E2ETestSuite(args.config)

    try:
        await suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        if suite.vg:
            await suite.vg.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
