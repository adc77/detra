"""Main VertiGuard client."""

import atexit
from typing import Any, Optional

import structlog

from detra.actions.incidents import IncidentManager
from detra.actions.notifications import NotificationManager
from detra.agents.monitor import AgentMonitor
from detra.config.loader import get_config, load_config, set_config
from detra.config.schema import VertiGuardConfig
from detra.dashboard.templates import get_dashboard_definition
from detra.dashboard.comprehensive_template import get_comprehensive_dashboard
from detra.decorators.trace import (
    set_evaluation_engine,
    set_datadog_client,
    trace as trace_decorator,
    workflow as workflow_decorator,
    llm as llm_decorator,
    task as task_decorator,
    agent as agent_decorator,
)
from detra.detection.monitors import MonitorManager
from detra.errors.tracker import ErrorTracker
from detra.evaluation.engine import EvaluationEngine
from detra.evaluation.gemini_judge import EvaluationResult, GeminiJudge
from detra.telemetry.datadog_client import DatadogClient
from detra.telemetry.llmobs_bridge import LLMObsBridge

logger = structlog.get_logger()

# Global client instance
_client: Optional["VertiGuard"] = None


class VertiGuard:
    """
    Main VertiGuard client for LLM observability.

    Usage:
        import detra

        vg = vertiguard.init("vertiguard.yaml")

        @vg.trace("extract_entities")
        def extract_entities(doc):
            return llm.complete(prompt)
    """

    def __init__(self, config: VertiGuardConfig):
        """
        Initialize the VertiGuard client.

        Args:
            config: VertiGuard configuration.
        """
        self.config = config
        set_config(config)

        # Initialize components
        self.datadog_client = DatadogClient(config.datadog)
        self.llmobs = LLMObsBridge(config)
        self.gemini_judge = GeminiJudge(config.gemini)
        self.evaluation_engine = EvaluationEngine(
            self.gemini_judge, config.security
        )
        self.monitor_manager = MonitorManager(self.datadog_client, config)
        self.notification_manager = NotificationManager(config.integrations)
        self.incident_manager = IncidentManager(
            self.datadog_client, self.notification_manager
        )

        # NEW: Error tracking (Sentry-style)
        self.error_tracker = ErrorTracker(
            self.datadog_client,
            environment=config.environment.value,
            release=config.version,
        )

        # NEW: Agent behavior monitoring
        self.agent_monitor = AgentMonitor(self.datadog_client)

        # Wire up decorators
        set_evaluation_engine(self.evaluation_engine)
        set_datadog_client(self.datadog_client)

        # Enable LLM Observability
        self.llmobs.enable()

        # Register cleanup
        atexit.register(self._cleanup)

        logger.info(
            "VertiGuard initialized",
            app_name=config.app_name,
            env=config.environment.value,
            nodes=list(config.nodes.keys()),
        )

    def _cleanup(self) -> None:
        """Cleanup on exit."""
        self.llmobs.flush()
        self.llmobs.disable()

    # =========================================================================
    # DECORATORS
    # =========================================================================

    def trace(self, node_name: str, **kwargs):
        """Create a trace decorator for a node."""
        return trace_decorator(node_name, **kwargs)

    def workflow(self, node_name: str, **kwargs):
        """Create a workflow trace decorator."""
        return workflow_decorator(node_name, **kwargs)

    def llm(self, node_name: str, **kwargs):
        """Create an LLM trace decorator."""
        return llm_decorator(node_name, **kwargs)

    def task(self, node_name: str, **kwargs):
        """Create a task trace decorator."""
        return task_decorator(node_name, **kwargs)

    def agent(self, node_name: str, **kwargs):
        """Create an agent trace decorator."""
        return agent_decorator(node_name, **kwargs)

    # =========================================================================
    # SETUP
    # =========================================================================

    async def setup_monitors(self, slack_channel: str = "llm-alerts") -> dict:
        """
        Create all default and custom monitors.

        Args:
            slack_channel: Slack channel for notifications.

        Returns:
            Dictionary with created monitor info.
        """
        results = {
            "default_monitors": [],
            "custom_monitors": [],
        }

        # Create default monitors
        results["default_monitors"] = await self.monitor_manager.create_default_monitors(
            slack_channel=slack_channel
        )

        # Create custom monitors from config
        if self.config.alerts:
            results["custom_monitors"] = await self.monitor_manager.create_custom_monitors(
                self.config.alerts
            )

        logger.info(
            "Monitors created",
            default=len(results["default_monitors"]),
            custom=len(results["custom_monitors"]),
        )

        return results

    async def setup_dashboard(self, comprehensive: bool = True) -> Optional[dict]:
        """
        Create the VertiGuard dashboard.

        Args:
            comprehensive: Use comprehensive 32-widget template (default: True).

        Returns:
            Dashboard info or None if disabled.
        """
        if not self.config.create_dashboard:
            return None

        if comprehensive:
            dashboard_def = get_comprehensive_dashboard(
                app_name=self.config.app_name,
                env=self.config.environment.value,
            )
        else:
            dashboard_def = get_dashboard_definition(
                app_name=self.config.app_name,
                env=self.config.environment.value,
            )

        if self.config.dashboard_name:
            dashboard_def["title"] = self.config.dashboard_name

        result = await self.datadog_client.create_dashboard(dashboard_def)

        if result:
            logger.info(
                "Dashboard created",
                title=result["title"],
                url=result.get("url"),
                widgets=len(dashboard_def.get("widgets", [])),
            )

        return result

    async def setup_all(self, slack_channel: str = "llm-alerts") -> dict:
        """
        Setup all monitors and dashboard.

        Args:
            slack_channel: Slack channel for notifications.

        Returns:
            Dictionary with setup results.
        """
        return {
            "monitors": await self.setup_monitors(slack_channel),
            "dashboard": await self.setup_dashboard(),
        }

    # =========================================================================
    # EVALUATION
    # =========================================================================

    async def evaluate(
        self,
        node_name: str,
        input_data: Any,
        output_data: Any,
        context: Optional[dict] = None,
    ) -> EvaluationResult:
        """
        Manually evaluate an LLM output.

        Args:
            node_name: Name of the node.
            input_data: Input to the LLM.
            output_data: Output from the LLM.
            context: Additional context.

        Returns:
            EvaluationResult with scores and details.

        Raises:
            ValueError: If node is not found in config.
        """
        node_config = self.config.nodes.get(node_name)
        if not node_config:
            raise ValueError(f"Unknown node: {node_name}")

        return await self.evaluation_engine.evaluate(
            node_config=node_config,
            input_data=input_data,
            output_data=output_data,
            context=context,
        )

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def flush(self) -> None:
        """Flush all pending telemetry."""
        self.llmobs.flush()

    async def submit_service_check(
        self, status: int = 0, message: str = ""
    ) -> bool:
        """
        Submit a service check (health check).

        Args:
            status: 0=OK, 1=Warning, 2=Critical, 3=Unknown.
            message: Check message.

        Returns:
            True if successful.
        """
        return await self.datadog_client.submit_service_check(
            check=f"vertiguard.{self.config.app_name}.health",
            status=status,
            message=message,
        )

    async def close(self) -> None:
        """Close the client and release resources."""
        self.flush()
        await self.datadog_client.close()
        await self.notification_manager.close()


# =========================================================================
# MODULE-LEVEL FUNCTIONS
# =========================================================================


def init(
    config_path: Optional[str] = None,
    env_file: Optional[str] = None,
    **kwargs,
) -> VertiGuard:
    """
    Initialize VertiGuard with configuration.

    Args:
        config_path: Path to vertiguard.yaml config file.
        env_file: Path to .env file (optional).
        **kwargs: Override config values.

    Returns:
        Initialized VertiGuard client.
    """
    global _client

    config = load_config(config_path=config_path, env_file=env_file)

    # Apply any overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    _client = VertiGuard(config)
    return _client


def get_client() -> VertiGuard:
    """
    Get the global VertiGuard client.

    Returns:
        The current VertiGuard client.

    Raises:
        RuntimeError: If client hasn't been initialized.
    """
    global _client
    if _client is None:
        raise RuntimeError("VertiGuard not initialized. Call vertiguard.init() first.")
    return _client


def is_initialized() -> bool:
    """Check if VertiGuard has been initialized."""
    return _client is not None
