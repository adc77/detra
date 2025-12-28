"""Detection rule definitions and engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RuleAction(str, Enum):
    """Actions to take when a rule matches."""
    ALERT = "alert"
    LOG = "log"
    BLOCK = "block"
    FLAG = "flag"
    INCIDENT = "incident"


class RulePriority(int, Enum):
    """Priority levels for rules."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


@dataclass
class RuleMatch:
    """Result of a rule match."""
    rule_name: str
    matched: bool
    value: Any = None
    message: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionRule:
    """Definition of a detection rule."""
    name: str
    description: str
    condition: Callable[[dict[str, Any]], bool]
    action: RuleAction
    priority: RulePriority = RulePriority.MEDIUM
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    notify: list[str] = field(default_factory=list)
    cooldown_seconds: int = 300  # Minimum time between alerts for same rule

    def evaluate(self, context: dict[str, Any]) -> RuleMatch:
        """
        Evaluate the rule against a context.

        Args:
            context: Context dictionary with evaluation data.

        Returns:
            RuleMatch with result.
        """
        if not self.enabled:
            return RuleMatch(rule_name=self.name, matched=False)

        try:
            matched = self.condition(context)
            return RuleMatch(
                rule_name=self.name,
                matched=matched,
                value=context.get("value"),
                message=f"Rule '{self.name}' triggered" if matched else None,
                details={"context": context},
            )
        except Exception as e:
            return RuleMatch(
                rule_name=self.name,
                matched=False,
                message=f"Rule evaluation error: {str(e)}",
            )


class DetectionRuleEngine:
    """
    Engine for evaluating detection rules.

    Manages a set of rules and evaluates them against
    incoming data.
    """

    def __init__(self):
        """Initialize the rule engine."""
        self._rules: dict[str, DetectionRule] = {}
        self._last_triggered: dict[str, float] = {}

    def add_rule(self, rule: DetectionRule) -> None:
        """
        Add a rule to the engine.

        Args:
            rule: Rule to add.
        """
        self._rules[rule.name] = rule

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule from the engine.

        Args:
            rule_name: Name of rule to remove.

        Returns:
            True if rule was found and removed.
        """
        if rule_name in self._rules:
            del self._rules[rule_name]
            return True
        return False

    def evaluate(
        self, context: dict[str, Any], rule_names: Optional[list[str]] = None
    ) -> list[RuleMatch]:
        """
        Evaluate rules against context.

        Args:
            context: Context dictionary with evaluation data.
            rule_names: Optional list of specific rules to evaluate.

        Returns:
            List of RuleMatch results for triggered rules.
        """
        import time

        matches = []
        current_time = time.time()

        rules_to_evaluate = (
            [self._rules[name] for name in rule_names if name in self._rules]
            if rule_names
            else list(self._rules.values())
        )

        # Sort by priority
        rules_to_evaluate.sort(key=lambda r: r.priority.value)

        for rule in rules_to_evaluate:
            if not rule.enabled:
                continue

            # Check cooldown
            last_triggered = self._last_triggered.get(rule.name, 0)
            if current_time - last_triggered < rule.cooldown_seconds:
                continue

            match = rule.evaluate(context)
            if match.matched:
                matches.append(match)
                self._last_triggered[rule.name] = current_time

        return matches

    def evaluate_all(self, context: dict[str, Any]) -> dict[str, RuleMatch]:
        """
        Evaluate all rules and return results by name.

        Args:
            context: Context dictionary.

        Returns:
            Dictionary of rule name to RuleMatch.
        """
        results = {}
        for name, rule in self._rules.items():
            results[name] = rule.evaluate(context)
        return results

    def get_rule(self, rule_name: str) -> Optional[DetectionRule]:
        """Get a rule by name."""
        return self._rules.get(rule_name)

    def list_rules(self) -> list[str]:
        """List all rule names."""
        return list(self._rules.keys())

    def enable_rule(self, rule_name: str) -> bool:
        """Enable a rule."""
        if rule_name in self._rules:
            self._rules[rule_name].enabled = True
            return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable a rule."""
        if rule_name in self._rules:
            self._rules[rule_name].enabled = False
            return True
        return False


# Pre-built detection rules
def create_adherence_rule(threshold: float = 0.85, action: RuleAction = RuleAction.FLAG) -> DetectionRule:
    """Create an adherence score detection rule."""
    return DetectionRule(
        name="low_adherence_score",
        description=f"Detect when adherence score drops below {threshold}",
        condition=lambda ctx: ctx.get("adherence_score", 1.0) < threshold,
        action=action,
        priority=RulePriority.HIGH,
        tags=["adherence", "quality"],
    )


def create_latency_rule(threshold_ms: int = 5000, action: RuleAction = RuleAction.ALERT) -> DetectionRule:
    """Create a latency detection rule."""
    return DetectionRule(
        name="high_latency",
        description=f"Detect when latency exceeds {threshold_ms}ms",
        condition=lambda ctx: ctx.get("latency_ms", 0) > threshold_ms,
        action=action,
        priority=RulePriority.MEDIUM,
        tags=["latency", "performance"],
    )


def create_error_rate_rule(threshold: float = 0.05, action: RuleAction = RuleAction.ALERT) -> DetectionRule:
    """Create an error rate detection rule."""
    return DetectionRule(
        name="high_error_rate",
        description=f"Detect when error rate exceeds {threshold*100}%",
        condition=lambda ctx: ctx.get("error_rate", 0) > threshold,
        action=action,
        priority=RulePriority.HIGH,
        tags=["errors", "reliability"],
    )


def create_security_rule(action: RuleAction = RuleAction.INCIDENT) -> DetectionRule:
    """Create a security issue detection rule."""
    return DetectionRule(
        name="security_issue",
        description="Detect security issues",
        condition=lambda ctx: ctx.get("security_issue_count", 0) > 0,
        action=action,
        priority=RulePriority.CRITICAL,
        tags=["security"],
    )


def create_flag_rate_rule(threshold: float = 0.10, action: RuleAction = RuleAction.ALERT) -> DetectionRule:
    """Create a flag rate detection rule."""
    return DetectionRule(
        name="high_flag_rate",
        description=f"Detect when flag rate exceeds {threshold*100}%",
        condition=lambda ctx: ctx.get("flag_rate", 0) > threshold,
        action=action,
        priority=RulePriority.HIGH,
        tags=["flags", "quality"],
    )
