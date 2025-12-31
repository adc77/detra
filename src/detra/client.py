"""Main detra client."""

import atexit
from typing import Any, Optional

import structlog

from detra.actions.incidents import IncidentManager
from detra.actions.notifications import NotificationManager
from detra.actions.cases import CaseManager
from detra.agents.monitor import AgentMonitor
from detra.config.loader import get_config, load_config, set_config
from detra.config.schema import detraConfig
from detra.dashboard.comprehensive_template import get_dashboard_definition, get_minimal_dashboard
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
from detra.optimization.root_cause import RootCauseAnalyzer
from detra.optimization.dspy_optimizer import DSpyOptimizer

logger = structlog.get_logger()

# Global client instance
_client: Optional["detra"] = None


class detra:
    """
    Main detra client for LLM observability.

    Usage:
        import detra

        vg = detra.init("detra.yaml")

        @vg.trace("extract_entities")
        def extract_entities(doc):
            return llm.complete(prompt)
    """

    def __init__(self, config: detraConfig):
        """
        Initialize the detra client.

        Args:
            config: detra configuration.
        """
        self.config = config
        set_config(config)

        # Initialize components
        self.datadog_client = DatadogClient(config.datadog)
        self.llmobs = LLMObsBridge(config)
        self.gemini_judge = GeminiJudge(config.gemini)
        self.evaluation_engine = EvaluationEngine(self.gemini_judge, config.security)
        self.monitor_manager = MonitorManager(self.datadog_client, config)
        self.notification_manager = NotificationManager(config.integrations)
        self.incident_manager = IncidentManager(self.datadog_client, self.notification_manager)

        # NEW: Error tracking (Sentry-style)
        self.error_tracker = ErrorTracker(
            self.datadog_client,
            environment=config.environment.value,
            release=config.version,
        )

        # NEW: Agent behavior monitoring
        self.agent_monitor = AgentMonitor(self.datadog_client)

        # NEW: Root cause analysis for errors
        if config.gemini and config.gemini.api_key:
            self.root_cause_analyzer = RootCauseAnalyzer(
                api_key=config.gemini.api_key,
                model=config.gemini.model or "gemini-2.5-flash",
            )
        else:
            self.root_cause_analyzer = None

        # NEW: DSPy prompt optimization
        if config.gemini and config.gemini.api_key:
            self.dspy_optimizer = DSpyOptimizer(
                model_name=config.gemini.model or "gemini-2.5-flash",
                api_key=config.gemini.api_key,
            )
        else:
            self.dspy_optimizer = None

        # NEW: Case management for tracking issues
        self.case_manager = CaseManager(max_cases=100)

        # Wire up decorators
        set_evaluation_engine(self.evaluation_engine)
        set_datadog_client(self.datadog_client)

        # Wire up optimization components
        from detra.decorators.trace import (
            set_root_cause_analyzer,
            set_dspy_optimizer,
            set_case_manager,
        )

        set_root_cause_analyzer(self.root_cause_analyzer)
        set_dspy_optimizer(self.dspy_optimizer)
        set_case_manager(self.case_manager)

        # Enable LLM Observability
        self.llmobs.enable()

        # Register cleanup
        atexit.register(self._cleanup)

        logger.info(
            "detra initialized",
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

    async def setup_dashboard(self, minimal: bool = False) -> Optional[dict]:
        """
        Create the detra dashboard.

        Args:
            minimal: Use minimal dashboard (fewer widgets). Default is full 42-widget dashboard.

        Returns:
            Dashboard info or None if disabled.
        """
        if not self.config.create_dashboard:
            return None

        if minimal:
            dashboard_def = get_minimal_dashboard(
                app_name=self.config.app_name,
                env=self.config.environment.value,
            )
        else:
            dashboard_def = get_dashboard_definition(
                app_name=self.config.app_name,
                env=self.config.environment.value,
            )

        dashboard_title = self.config.dashboard_name or dashboard_def.get("title", "")
        dashboard_def["title"] = dashboard_title

        # Check if dashboard already exists
        existing_dashboards = await self.datadog_client.list_dashboards(
            title_filter=dashboard_title
        )
        for existing in existing_dashboards:
            if existing["title"] == dashboard_title:
                logger.info(
                    "Dashboard already exists, skipping creation",
                    title=dashboard_title,
                    id=existing.get("id"),
                    url=existing.get("url"),
                )
                return {
                    "id": existing.get("id"),
                    "title": existing["title"],
                    "url": existing.get("url"),
                }

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

    async def submit_service_check(self, status: int = 0, message: str = "") -> bool:
        """
        Submit a service check (health check).

        Args:
            status: 0=OK, 1=Warning, 2=Critical, 3=Unknown.
            message: Check message.

        Returns:
            True if successful.
        """
        return await self.datadog_client.submit_service_check(
            check=f"detra.{self.config.app_name}.health",
            status=status,
            message=message,
        )

    async def close(self) -> None:
        """Close the client and release resources."""
        self.flush()
        await self.datadog_client.close()
        await self.notification_manager.close()

    # =========================================================================
    # ROOT CAUSE ANALYSIS
    # =========================================================================

    async def analyze_error_root_cause(
        self,
        error: Exception,
        context: Optional[dict] = None,
        input_data: Any = None,
        output_data: Any = None,
    ) -> Optional[dict]:
        """
        Analyze an error and provide root cause analysis.

        Args:
            error: The exception that occurred.
            context: Additional context about error.
            input_data: Input that caused error.
            output_data: Output (if any) before error.

        Returns:
            Root cause analysis dict with suggested fixes and files to check.
        """
        if not self.root_cause_analyzer:
            return {"error": "Root cause analyzer not configured"}

        try:
            return await self.root_cause_analyzer.analyze_error(
                error=error,
                context=context or {},
                node_name=None,
                input_data=input_data,
                output_data=output_data,
            )
        except Exception as e:
            logger.error("Root cause analysis failed", error=str(e))
            return {"error": str(e)}

    # =========================================================================
    # PROMPT OPTIMIZATION
    # =========================================================================

    async def optimize_prompt(
        self,
        node_name: str,
        original_prompt: str,
        failure_reason: str,
        failed_examples: list = None,
    ) -> Optional[dict]:
        """
        Optimize a failing prompt using DSPy.

        Args:
            node_name: Name of node.
            original_prompt: Original failing prompt.
            failure_reason: Why the prompt is failing.
            failed_examples: Examples of failures.

        Returns:
            Optimization result with improved prompt and changes made.
        """
        if not self.dspy_optimizer:
            return {"error": "DSPy optimizer not configured"}

        try:
            node_config = self.config.nodes.get(node_name)
            return await self.dspy_optimizer.optimize_prompt(
                original_prompt=original_prompt,
                failure_reason=failure_reason,
                expected_behaviors=node_config.expected_behaviors if node_config else [],
                unexpected_behaviors=node_config.unexpected_behaviors if node_config else [],
                failed_examples=failed_examples or [],
                max_iterations=3,
            )
        except Exception as e:
            logger.error("Prompt optimization failed", error=str(e))
            return {"error": str(e)}

    # =========================================================================
    # CASE MANAGEMENT
    # =========================================================================

    def create_case(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        category: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> dict:
        """
        Create a new case for tracking.

        Args:
            title: Case title.
            description: Case description.
            priority: Priority level (critical, high, medium, low).
            category: Issue category.
            tags: Additional tags.

        Returns:
            Created case dict.
        """
        from detra.actions.cases import CasePriority

        priority_map = {
            "critical": CasePriority.CRITICAL,
            "high": CasePriority.HIGH,
            "medium": CasePriority.MEDIUM,
            "low": CasePriority.LOW,
        }

        case = self.case_manager.create_case(
            title=title,
            description=description,
            priority=priority_map.get(priority, CasePriority.MEDIUM),
            category=category,
            tags=tags,
        )

        return case.to_dict()

    def get_cases(self, status=None, priority=None, limit=50):
        """Get list of cases with optional filtering."""
        from detra.actions.cases import CaseStatus

        status_map = {
            "open": CaseStatus.OPEN,
            "in_progress": CaseStatus.IN_PROGRESS,
            "resolved": CaseStatus.RESOLVED,
            "closed": CaseStatus.CLOSED,
        }

        from detra.actions.cases import CasePriority
        priority_map = {
            "critical": CasePriority.CRITICAL,
            "high": CasePriority.HIGH,
            "medium": CasePriority.MEDIUM,
            "low": CasePriority.LOW,
        }

        cases = self.case_manager.list_cases(
            status=status_map.get(status) if status else None,
            priority=priority_map.get(priority) if priority else None,
            limit=limit,
        )

        return [c.to_dict() for c in cases]


# =========================================================================
# MODULE-LEVEL FUNCTIONS
# =========================================================================


def init(
    config_path: Optional[str] = None,
    env_file: Optional[str] = None,
    **kwargs,
) -> detra:
    """
    Initialize detra with configuration.

    Args:
        config_path: Path to detra.yaml config file.
        env_file: Path to .env file (optional).
        **kwargs: Override config values.

    Returns:
        Initialized detra client.
    """
    global _client

    config = load_config(config_path=config_path, env_file=env_file)

    # Apply any overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    _client = detra(config)
    return _client


def get_client() -> detra:
    """
    Get the global detra client.

    Returns:
        The current detra client.

    Raises:
        RuntimeError: If client hasn't been initialized.
    """
    global _client
    if _client is None:
        raise RuntimeError("detra not initialized. Call detra.init() first.")
    return _client


def is_initialized() -> bool:
    """Check if detra has been initialized."""
    return _client is not None