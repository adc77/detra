"""Tool call tracking and analysis."""

from typing import Dict, List, Any, Optional
from collections import Counter
import structlog

logger = structlog.get_logger()


class ToolCallTracker:
    """
    Tracks tool usage patterns across agents.

    Monitors:
    - Most frequently used tools
    - Tool success/failure rates
    - Tool latency statistics
    - Tool call sequences
    """

    def __init__(self):
        """Initialize tool call tracker."""
        self._tool_calls: List[Dict[str, Any]] = []

    def record_tool_call(
        self,
        tool_name: str,
        agent_name: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None,
    ):
        """
        Record a tool call.

        Args:
            tool_name: Name of the tool.
            agent_name: Agent that called the tool.
            success: Whether the call succeeded.
            latency_ms: Call latency.
            error: Error message if failed.
        """
        self._tool_calls.append({
            "tool_name": tool_name,
            "agent_name": agent_name,
            "success": success,
            "latency_ms": latency_ms,
            "error": error,
        })

    def get_tool_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get usage statistics for each tool.

        Returns:
            Dictionary mapping tool name to stats.
        """
        stats = {}

        for call in self._tool_calls:
            tool = call["tool_name"]

            if tool not in stats:
                stats[tool] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_latency_ms": 0,
                    "errors": [],
                }

            stats[tool]["total_calls"] += 1

            if call["success"]:
                stats[tool]["successful_calls"] += 1
            else:
                stats[tool]["failed_calls"] += 1
                if call["error"]:
                    stats[tool]["errors"].append(call["error"])

            stats[tool]["total_latency_ms"] += call["latency_ms"]

        # Calculate averages
        for tool, data in stats.items():
            if data["total_calls"] > 0:
                data["avg_latency_ms"] = data["total_latency_ms"] / data["total_calls"]
                data["success_rate"] = data["successful_calls"] / data["total_calls"]

        return stats

    def get_most_used_tools(self, limit: int = 10) -> List[tuple]:
        """
        Get most frequently used tools.

        Args:
            limit: Number of tools to return.

        Returns:
            List of (tool_name, count) tuples.
        """
        tool_names = [call["tool_name"] for call in self._tool_calls]
        counter = Counter(tool_names)
        return counter.most_common(limit)

    def get_failing_tools(self, min_failures: int = 3) -> List[str]:
        """
        Get tools that are failing frequently.

        Args:
            min_failures: Minimum failures to include.

        Returns:
            List of tool names.
        """
        failed_tools = [
            call["tool_name"]
            for call in self._tool_calls
            if not call["success"]
        ]

        counter = Counter(failed_tools)
        return [
            tool
            for tool, count in counter.items()
            if count >= min_failures
        ]

    def get_slow_tools(self, threshold_ms: float = 1000) -> List[tuple]:
        """
        Get tools with high average latency.

        Args:
            threshold_ms: Latency threshold.

        Returns:
            List of (tool_name, avg_latency) tuples.
        """
        stats = self.get_tool_usage_stats()

        slow_tools = [
            (tool, data["avg_latency_ms"])
            for tool, data in stats.items()
            if data["avg_latency_ms"] > threshold_ms
        ]

        return sorted(slow_tools, key=lambda x: x[1], reverse=True)
