"""
Agent behavior monitoring for tracking multi-step agent workflows.

Monitors:
- Agent decision chains (thought -> action -> observation)
- Tool usage patterns
- ReAct loop iterations
- Agent failures and recoveries
- Unexpected agent behaviors
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

import structlog

from detra.telemetry.datadog_client import DatadogClient

logger = structlog.get_logger()


class AgentStepType(str, Enum):
    """Types of agent steps."""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    FINAL_ANSWER = "final_answer"


@dataclass
class AgentStep:
    """Single step in agent workflow."""
    step_type: AgentStepType
    content: Any
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None
    tool_input: Optional[Any] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


@dataclass
class AgentWorkflow:
    """Complete agent workflow/chain."""
    workflow_id: str
    agent_name: str
    steps: List[AgentStep] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    final_output: Optional[Any] = None
    status: str = "running"  # running, completed, failed
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: AgentStep):
        """Add a step to the workflow."""
        self.steps.append(step)

    def complete(self, final_output: Any):
        """Mark workflow as completed."""
        self.final_output = final_output
        self.status = "completed"
        self.end_time = time.time()

    def fail(self, error: str):
        """Mark workflow as failed."""
        self.status = "failed"
        self.end_time = time.time()
        self.metadata["error"] = error

    def get_duration_ms(self) -> float:
        """Get total workflow duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

    def get_tool_calls(self) -> List[AgentStep]:
        """Get all tool call steps."""
        return [s for s in self.steps if s.step_type == AgentStepType.TOOL_CALL]

    def get_decisions(self) -> List[AgentStep]:
        """Get all decision steps."""
        return [s for s in self.steps if s.step_type == AgentStepType.DECISION]


class AgentMonitor:
    """
    Monitor agent behaviors and workflows.

    Tracks:
    - ReAct loops (Thought -> Action -> Observation)
    - Tool usage patterns
    - Decision chains
    - Agent failures
    - Unexpected behaviors (infinite loops, tool failures, etc.)

    Usage:
        monitor = AgentMonitor(datadog_client)

        # Start tracking a workflow
        workflow_id = monitor.start_workflow("customer_support_agent")

        # Track steps
        monitor.track_thought(workflow_id, "User wants to cancel order")
        monitor.track_action(workflow_id, "search_orders", {"user_id": "123"})
        monitor.track_observation(workflow_id, "Found order #456")

        # Track tool calls
        monitor.track_tool_call(
            workflow_id,
            tool_name="cancel_order",
            tool_input={"order_id": "456"},
            tool_output={"success": True}
        )

        # Complete workflow
        monitor.complete_workflow(workflow_id, final_answer="Order cancelled")
    """

    def __init__(
        self,
        datadog_client: DatadogClient,
        max_steps_warning: int = 20,
        max_tool_calls_warning: int = 10,
    ):
        """
        Initialize agent monitor.

        Args:
            datadog_client: Datadog client for telemetry.
            max_steps_warning: Warn if workflow exceeds this many steps.
            max_tool_calls_warning: Warn if agent makes too many tool calls.
        """
        self.datadog = datadog_client
        self.max_steps_warning = max_steps_warning
        self.max_tool_calls_warning = max_tool_calls_warning

        self._workflows: Dict[str, AgentWorkflow] = {}

    def start_workflow(
        self,
        agent_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start tracking a new agent workflow.

        Args:
            agent_name: Name of the agent.
            metadata: Additional metadata.

        Returns:
            Workflow ID for tracking.
        """
        workflow_id = f"{agent_name}_{int(time.time() * 1000)}"

        workflow = AgentWorkflow(
            workflow_id=workflow_id,
            agent_name=agent_name,
            metadata=metadata or {},
        )

        self._workflows[workflow_id] = workflow

        logger.info(
            "Agent workflow started",
            workflow_id=workflow_id,
            agent=agent_name,
        )

        return workflow_id

    def track_thought(
        self,
        workflow_id: str,
        thought: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Track an agent's thought/reasoning step.

        Args:
            workflow_id: Workflow ID.
            thought: The agent's thought/reasoning.
            metadata: Additional metadata.
        """
        step = AgentStep(
            step_type=AgentStepType.THOUGHT,
            content=thought,
            metadata=metadata or {},
        )

        self._add_step(workflow_id, step)

    def track_action(
        self,
        workflow_id: str,
        action: str,
        action_input: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Track an agent's action.

        Args:
            workflow_id: Workflow ID.
            action: The action being taken.
            action_input: Input to the action.
            metadata: Additional metadata.
        """
        step = AgentStep(
            step_type=AgentStepType.ACTION,
            content=action,
            tool_input=action_input,
            metadata=metadata or {},
        )

        self._add_step(workflow_id, step)

    def track_observation(
        self,
        workflow_id: str,
        observation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Track an agent's observation (result of action).

        Args:
            workflow_id: Workflow ID.
            observation: The observation/result.
            metadata: Additional metadata.
        """
        step = AgentStep(
            step_type=AgentStepType.OBSERVATION,
            content=observation,
            metadata=metadata or {},
        )

        self._add_step(workflow_id, step)

    def track_tool_call(
        self,
        workflow_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """
        Track a tool call made by the agent.

        Args:
            workflow_id: Workflow ID.
            tool_name: Name of the tool.
            tool_input: Input to the tool.
            tool_output: Output from the tool.
            latency_ms: Tool execution latency.
            error: Error if tool failed.
        """
        step = AgentStep(
            step_type=AgentStepType.TOOL_CALL,
            content=f"Called {tool_name}",
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            latency_ms=latency_ms,
            error=error,
        )

        self._add_step(workflow_id, step)

        # Check for too many tool calls
        workflow = self._workflows.get(workflow_id)
        if workflow:
            tool_calls = workflow.get_tool_calls()
            if len(tool_calls) > self.max_tool_calls_warning:
                logger.warning(
                    "Agent making excessive tool calls",
                    workflow_id=workflow_id,
                    tool_calls=len(tool_calls),
                    max_expected=self.max_tool_calls_warning,
                )

    def track_decision(
        self,
        workflow_id: str,
        decision: str,
        rationale: Optional[str] = None,
        confidence: Optional[float] = None,
    ):
        """
        Track an agent's decision.

        Args:
            workflow_id: Workflow ID.
            decision: The decision made.
            rationale: Reasoning behind decision.
            confidence: Confidence score (0-1).
        """
        step = AgentStep(
            step_type=AgentStepType.DECISION,
            content=decision,
            metadata={
                "rationale": rationale,
                "confidence": confidence,
            },
        )

        self._add_step(workflow_id, step)

    def complete_workflow(
        self,
        workflow_id: str,
        final_output: Any,
    ):
        """
        Mark a workflow as completed.

        Args:
            workflow_id: Workflow ID.
            final_output: The final output/answer.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            logger.warning("Unknown workflow", workflow_id=workflow_id)
            return

        workflow.complete(final_output)

        # Log completion
        logger.info(
            "Agent workflow completed",
            workflow_id=workflow_id,
            agent=workflow.agent_name,
            steps=len(workflow.steps),
            duration_ms=workflow.get_duration_ms(),
            tool_calls=len(workflow.get_tool_calls()),
        )

        # Submit telemetry (fire-and-forget to avoid blocking)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._submit_workflow_telemetry(workflow))
                asyncio.create_task(self._check_workflow_anomalies(workflow))
        except Exception:
            pass  # Don't fail workflow completion if telemetry fails

    def fail_workflow(
        self,
        workflow_id: str,
        error: str,
    ):
        """
        Mark a workflow as failed.

        Args:
            workflow_id: Workflow ID.
            error: Error description.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return

        workflow.fail(error)

        logger.error(
            "Agent workflow failed",
            workflow_id=workflow_id,
            agent=workflow.agent_name,
            steps=len(workflow.steps),
            error=error,
        )

        # Submit telemetry (fire-and-forget)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._submit_workflow_telemetry(workflow))
        except Exception:
            pass

    def get_workflow(self, workflow_id: str) -> Optional[AgentWorkflow]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_active_workflows(self) -> List[AgentWorkflow]:
        """Get all currently running workflows."""
        return [
            w for w in self._workflows.values()
            if w.status == "running"
        ]

    def _add_step(self, workflow_id: str, step: AgentStep):
        """Add a step to a workflow."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            logger.warning("Unknown workflow", workflow_id=workflow_id)
            return

        workflow.add_step(step)

        # Check for too many steps (possible infinite loop)
        if len(workflow.steps) > self.max_steps_warning:
            logger.warning(
                "Agent workflow has excessive steps",
                workflow_id=workflow_id,
                steps=len(workflow.steps),
                max_expected=self.max_steps_warning,
            )

    async def _submit_workflow_telemetry(self, workflow: AgentWorkflow):
        """Submit workflow telemetry to Datadog."""
        try:
            # Submit metrics
            await self.datadog.submit_metrics([
                {
                    "metric": "vertiguard.agent.workflow.duration_ms",
                    "type": "gauge",
                    "points": [[int(time.time()), workflow.get_duration_ms()]],
                    "tags": [
                        f"agent:{workflow.agent_name}",
                        f"status:{workflow.status}",
                    ],
                },
                {
                    "metric": "vertiguard.agent.workflow.steps",
                    "type": "gauge",
                    "points": [[int(time.time()), len(workflow.steps)]],
                    "tags": [f"agent:{workflow.agent_name}"],
                },
                {
                    "metric": "vertiguard.agent.tool_calls",
                    "type": "gauge",
                    "points": [[int(time.time()), len(workflow.get_tool_calls())]],
                    "tags": [f"agent:{workflow.agent_name}"],
                },
            ])

            # Submit event
            await self.datadog.submit_event(
                title=f"Agent Workflow: {workflow.agent_name}",
                text=f"""## Workflow {workflow.status}

**Workflow ID**: `{workflow.workflow_id}`
**Steps**: {len(workflow.steps)}
**Tool Calls**: {len(workflow.get_tool_calls())}
**Duration**: {workflow.get_duration_ms():.0f}ms

### Workflow Steps
{self._format_workflow_steps(workflow)}
""",
                alert_type="info" if workflow.status == "completed" else "error",
                tags=[
                    f"agent:{workflow.agent_name}",
                    f"workflow_id:{workflow.workflow_id}",
                    f"status:{workflow.status}",
                ],
            )

        except Exception as e:
            logger.error("Failed to submit workflow telemetry", error=str(e))

    def _format_workflow_steps(self, workflow: AgentWorkflow) -> str:
        """Format workflow steps for display."""
        lines = []
        for i, step in enumerate(workflow.steps[:10], 1):  # Show first 10
            lines.append(f"{i}. [{step.step_type.value}] {str(step.content)[:100]}")
        if len(workflow.steps) > 10:
            lines.append(f"... and {len(workflow.steps) - 10} more steps")
        return "\n".join(lines)

    async def _check_workflow_anomalies(self, workflow: AgentWorkflow):
        """Check for anomalous agent behavior."""
        anomalies = []

        # Check for excessive steps
        if len(workflow.steps) > self.max_steps_warning:
            anomalies.append({
                "type": "excessive_steps",
                "description": f"Workflow took {len(workflow.steps)} steps (expected < {self.max_steps_warning})",
                "severity": "high",
            })

        # Check for excessive tool calls
        tool_calls = workflow.get_tool_calls()
        if len(tool_calls) > self.max_tool_calls_warning:
            anomalies.append({
                "type": "excessive_tool_calls",
                "description": f"Agent made {len(tool_calls)} tool calls (expected < {self.max_tool_calls_warning})",
                "severity": "medium",
            })

        # Check for repeated tool failures
        failed_tools = [s for s in tool_calls if s.error]
        if len(failed_tools) > 3:
            anomalies.append({
                "type": "repeated_tool_failures",
                "description": f"{len(failed_tools)} tool calls failed",
                "severity": "high",
            })

        # Submit anomalies
        if anomalies:
            logger.warning(
                "Agent workflow anomalies detected",
                workflow_id=workflow.workflow_id,
                anomalies=len(anomalies),
            )

            for anomaly in anomalies:
                await self.datadog.submit_event(
                    title=f"Agent Anomaly: {anomaly['type']}",
                    text=f"""## {anomaly['description']}

**Workflow**: {workflow.workflow_id}
**Agent**: {workflow.agent_name}
**Severity**: {anomaly['severity']}
""",
                    alert_type="warning",
                    tags=[
                        f"agent:{workflow.agent_name}",
                        f"anomaly_type:{anomaly['type']}",
                    ],
                )
