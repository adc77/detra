"""Workflow tracking and visualization for agent chains."""

from typing import Dict, List
import structlog

logger = structlog.get_logger()


class WorkflowTracker:
    """
    Tracks agent workflows for visualization and analysis.

    Creates a DAG (directed acyclic graph) representation of:
    - Agent steps
    - Decision points
    - Tool calls
    - Branching logic
    """

    def __init__(self):
        """Initialize workflow tracker."""
        self._workflows: Dict[str, Dict] = {}

    def create_workflow_graph(self, workflow_id: str, workflow_data: Dict) -> Dict:
        """
        Create a graph representation of a workflow.

        Args:
            workflow_id: Workflow ID.
            workflow_data: Workflow data with steps.

        Returns:
            Graph structure with nodes and edges.
        """
        nodes = []
        edges = []

        steps = workflow_data.get("steps", [])

        for i, step in enumerate(steps):
            # Create node
            node = {
                "id": f"step_{i}",
                "type": step.get("step_type"),
                "content": str(step.get("content", ""))[:100],
                "timestamp": step.get("timestamp"),
            }

            # Add tool-specific info
            if step.get("tool_name"):
                node["tool_name"] = step["tool_name"]
                node["tool_latency_ms"] = step.get("latency_ms")

            nodes.append(node)

            # Create edge to next step
            if i > 0:
                edges.append({
                    "from": f"step_{i-1}",
                    "to": f"step_{i}",
                })

        return {
            "workflow_id": workflow_id,
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_steps": len(steps),
                "status": workflow_data.get("status"),
            },
        }

    def get_critical_path(self, workflow_graph: Dict) -> List[str]:
        """
        Get the critical path through the workflow (longest path).

        Args:
            workflow_graph: Workflow graph.

        Returns:
            List of node IDs in critical path.
        """
        # Simple implementation - return all nodes in order
        return [node["id"] for node in workflow_graph["nodes"]]
