#!/usr/bin/env python3
"""
Comprehensive Monitoring Example

Demonstrates all detra monitoring capabilities:
1. Traditional error tracking (Sentry-style)
2. LLM prompt/output monitoring
3. Agent behavior tracking (tool calls, decisions, workflows)
4. Root cause analysis
5. DSPy prompt optimization

This shows detra as a complete observability solution.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import google.genai as genai
import structlog

import detra
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()


class CustomerSupportAgent:
    """
    Example AI agent with comprehensive monitoring.

    This agent demonstrates:
    - Error tracking for code failures
    - LLM monitoring for prompt quality
    - Agent workflow tracking for multi-step processes
    """

    def __init__(self, config_path: str):
        """Initialize agent with detra."""
        # Initialize detra
        self.vg = detra.init(config_path)

        # Initialize Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

        logger.info("CustomerSupportAgent initialized")

    # =========================================================================
    # EXAMPLE 1: Traditional Error Tracking (Sentry-style)
    # =========================================================================

    async def process_order_with_error_tracking(self, order_id: str) -> dict:
        """
        Process an order with automatic error tracking.

        Demonstrates:
        - Automatic exception capture
        - Breadcrumb tracking (events leading to error)
        - User context
        - Error grouping and deduplication
        """
        # Set user context for errors
        self.vg.error_tracker.set_user(
            user_id=order_id,
            email=f"customer_{order_id}@example.com",
        )

        # Add breadcrumb
        self.vg.error_tracker.add_breadcrumb(
            message=f"Started processing order {order_id}",
            category="order_processing",
            level="info",
        )

        try:
            # Add more breadcrumbs as we go
            self.vg.error_tracker.add_breadcrumb(
                message="Fetching order from database",
                category="database",
            )

            # Simulate database call
            order = await self._fetch_order(order_id)

            self.vg.error_tracker.add_breadcrumb(
                message="Validating order items",
                category="validation",
            )

            # This might raise an error
            await self._validate_order(order)

            return {"status": "success", "order": order}

        except Exception as e:
            # Automatic error capture with context
            error_id = self.vg.error_tracker.capture_exception(
                e,
                level="error",
                context={"order_id": order_id},
                tags=["service:order_processing"],
            )

            logger.error("Order processing failed", error_id=error_id)
            return {"status": "error", "error_id": error_id}

    async def _fetch_order(self, order_id: str) -> dict:
        """Simulate fetching order."""
        # Simulate random failures
        import random
        if random.random() < 0.1:
            raise ValueError(f"Order not found: {order_id}")

        return {"order_id": order_id, "items": ["item1", "item2"]}

    async def _validate_order(self, order: dict):
        """Simulate order validation."""
        if not order.get("items"):
            raise ValueError("Order has no items")

    # =========================================================================
    # EXAMPLE 2: LLM Monitoring (Prompt Quality)
    # =========================================================================

    @detra.trace("generate_response")
    async def generate_support_response(
        self,
        customer_query: str,
        context: dict,
    ) -> str:
        """
        Generate customer support response.

        Demonstrates:
        - LLM prompt/output monitoring
        - Adherence scoring
        - Hallucination detection
        - PII detection
        """
        prompt = f"""You are a helpful customer support agent.

Context: {context}

Customer Query: {customer_query}

Provide a helpful, accurate response. Only use information from the context.
Do not make up information or include personal data.

Response:"""

        # This is automatically traced and evaluated by detra
        response = await self._call_llm(prompt)

        return response

    # =========================================================================
    # EXAMPLE 3: Agent Workflow Tracking (Multi-Step Process)
    # =========================================================================

    async def handle_customer_request(
        self,
        customer_id: str,
        request: str,
    ) -> dict:
        """
        Handle a customer request using multi-step agent workflow.

        Demonstrates:
        - Workflow tracking (thought -> action -> observation)
        - Tool call monitoring
        - Decision tracking
        - Anomaly detection (too many steps, failed tools)
        """
        # Start workflow tracking
        workflow_id = self.vg.agent_monitor.start_workflow(
            agent_name="customer_support_agent",
            metadata={"customer_id": customer_id},
        )

        try:
            # Step 1: Analyze request
            self.vg.agent_monitor.track_thought(
                workflow_id,
                thought="Customer wants to check order status. Need to fetch order details.",
            )

            self.vg.agent_monitor.track_decision(
                workflow_id,
                decision="fetch_order_status",
                rationale="Query mentions order status",
                confidence=0.95,
            )

            # Step 2: Take action (tool call)
            self.vg.agent_monitor.track_action(
                workflow_id,
                action="search_orders",
                action_input={"customer_id": customer_id},
            )

            # Simulate tool call
            tool_start = asyncio.get_event_loop().time()
            order_data = await self._tool_search_orders(customer_id)
            tool_latency = (asyncio.get_event_loop().time() - tool_start) * 1000

            # Track tool call
            self.vg.agent_monitor.track_tool_call(
                workflow_id,
                tool_name="search_orders",
                tool_input={"customer_id": customer_id},
                tool_output=order_data,
                latency_ms=tool_latency,
            )

            # Step 3: Observe results
            self.vg.agent_monitor.track_observation(
                workflow_id,
                observation=f"Found {len(order_data)} orders for customer",
            )

            # Step 4: Generate final response
            self.vg.agent_monitor.track_thought(
                workflow_id,
                thought="Now I can formulate a response with order status",
            )

            final_response = await self.generate_support_response(
                customer_query=request,
                context={"orders": order_data},
            )

            # Complete workflow
            self.vg.agent_monitor.complete_workflow(
                workflow_id,
                final_output=final_response,
            )

            return {
                "status": "success",
                "response": final_response,
                "workflow_id": workflow_id,
            }

        except Exception as e:
            # Mark workflow as failed
            self.vg.agent_monitor.fail_workflow(
                workflow_id,
                error=str(e),
            )

            # Also track error
            self.vg.error_tracker.capture_exception(e)

            return {"status": "error", "error": str(e)}

    async def _tool_search_orders(self, customer_id: str) -> list:
        """Simulate order search tool."""
        return [
            {"order_id": "123", "status": "shipped"},
            {"order_id": "456", "status": "delivered"},
        ]

    # =========================================================================
    # EXAMPLE 4: Root Cause Analysis + Prompt Optimization
    # =========================================================================

    async def handle_low_quality_response(
        self,
        query: str,
        response: str,
        score: float,
    ):
        """
        Handle a low-quality LLM response.

        Demonstrates:
        - Root cause analysis for evaluation failures
        - DSPy prompt optimization
        - Actionable improvement suggestions
        """
        if score < 0.75:
            logger.warning(
                "Low quality response detected",
                score=score,
                query=query[:100],
            )

            # Use root cause analyzer
            from detra.optimization.root_cause import RootCauseAnalyzer

            analyzer = RootCauseAnalyzer(
                api_key=os.getenv("GOOGLE_API_KEY")
            )

            analysis = await analyzer.analyze_evaluation_failure(
                node_name="generate_response",
                score=score,
                failed_behaviors=["Response quality below threshold"],
                input_data=query,
                output_data=response,
                expected_behaviors=[
                    "Must be helpful and accurate",
                    "Must not include PII",
                    "Must cite sources",
                ],
            )

            logger.info(
                "Root cause analysis complete",
                root_cause=analysis.get("root_cause"),
                suggested_fixes=len(analysis.get("suggested_fixes", [])),
            )

            # Optionally: Use DSPy to optimize prompt
            # (This would generate an improved prompt version)

    # Helper methods

    def _generate_content_sync(self, prompt: str) -> str:
        """Synchronous helper to generate content and parse response."""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
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

    async def _call_llm(self, prompt: str) -> str:
        """Call Gemini API."""
        return await asyncio.to_thread(self._generate_content_sync, prompt)


async def main():
    """Run comprehensive monitoring demo."""
    print("\n" + "="*60)
    print("COMPREHENSIVE MONITORING DEMO")
    print("="*60 + "\n")

    # Get config path
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "examples" / "legal_analyzer" / "detra.yaml"

    # Initialize agent
    agent = CustomerSupportAgent(str(config_path))

    print("1. Testing error tracking (Sentry-style)...")
    for i in range(5):
        result = await agent.process_order_with_error_tracking(f"order_{i}")
        print(f"   Order {i}: {result['status']}")

    print("\n2. Testing LLM monitoring...")
    response = await agent.generate_support_response(
        customer_query="What's my order status?",
        context={"order_id": "123", "status": "shipped"},
    )
    print(f"   Response: {response[:100]}...")

    print("\n3. Testing agent workflow tracking...")
    result = await agent.handle_customer_request(
        customer_id="cust_001",
        request="Can you check my order status?",
    )
    print(f"   Workflow completed: {result['workflow_id']}")

    print("\n4. Testing root cause analysis...")
    await agent.handle_low_quality_response(
        query="Test query",
        response="Low quality response",
        score=0.60,
    )

    # Print error summary
    print("\n" + "="*60)
    print("ERROR TRACKING SUMMARY")
    print("="*60)
    errors = agent.vg.error_tracker.get_all_errors()
    print(f"Total unique errors: {len(errors)}")
    print(f"Total occurrences: {agent.vg.error_tracker.total_errors}")

    # Print agent workflow summary
    print("\n" + "="*60)
    print("AGENT WORKFLOW SUMMARY")
    print("="*60)
    active = agent.vg.agent_monitor.get_active_workflows()
    print(f"Active workflows: {len(active)}")

    print("\n" + "="*60)
    print("Check your Datadog dashboard for:")
    print("  - Error events with full context")
    print("  - Agent workflow traces")
    print("  - LLM adherence scores")
    print("  - Tool usage statistics")
    print("="*60 + "\n")

    # Cleanup
    await agent.vg.close()


if __name__ == "__main__":
    asyncio.run(main())
