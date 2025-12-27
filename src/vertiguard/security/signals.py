"""Security signal definitions and management."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class SignalSeverity(str, Enum):
    """Severity levels for security signals."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SignalType(str, Enum):
    """Types of security signals."""
    PII_DETECTED = "pii_detected"
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    SENSITIVE_DATA_LEAK = "sensitive_data_leak"
    HARMFUL_CONTENT = "harmful_content"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    AUTHENTICATION_FAILURE = "authentication_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class SignalStatus(str, Enum):
    """Status of security signals."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass
class SecuritySignal:
    """A security signal representing a detected issue."""
    signal_type: SignalType | str
    severity: SignalSeverity
    message: str
    node_name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    details: dict[str, Any] = field(default_factory=dict)
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    acknowledged: bool = False
    status: SignalStatus = SignalStatus.OPEN
    title: Optional[str] = None
    description: Optional[str] = None
    source_node: Optional[str] = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    acknowledged_by: Optional[str] = None

    def __post_init__(self):
        """Set defaults after initialization."""
        # Convert string signal_type to enum if needed
        if isinstance(self.signal_type, str):
            try:
                self.signal_type = SignalType(self.signal_type)
            except ValueError:
                self.signal_type = SignalType.ANOMALOUS_BEHAVIOR

        if self.source_node is None:
            self.source_node = self.node_name
        if self.node_name is None:
            self.node_name = self.source_node
        if self.title is None:
            self.title = self.message
        if self.description is None:
            self.description = self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "node_name": self.node_name,
            "timestamp": self.timestamp,
            "details": self.details,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "acknowledged": self.acknowledged,
        }

    @classmethod
    def from_scan_result(
        cls,
        scan_result: Any,
        node_name: Optional[str] = None,
    ) -> list["SecuritySignal"]:
        """
        Create security signals from a scan result.

        Args:
            scan_result: ScanResult from a security scanner.
            node_name: Name of the node where scan was performed.

        Returns:
            List of SecuritySignal instances.
        """
        if not scan_result.detected:
            return []

        signals = []
        for finding in scan_result.findings:
            signal_type = cls._map_to_signal_type(scan_result.scanner_name)
            severity = cls._map_severity(finding.get("severity", "medium"))

            signals.append(
                cls(
                    signal_type=signal_type,
                    severity=severity,
                    message=f"{scan_result.scanner_name}: {finding.get('description', finding.get('type', 'Unknown issue'))}",
                    node_name=node_name,
                    details=finding,
                    evidence=finding.get("evidence"),
                )
            )

        return signals

    @staticmethod
    def _map_to_signal_type(scanner_name: str) -> SignalType:
        """Map scanner name to signal type."""
        mapping = {
            "pii_detection": SignalType.PII_DETECTED,
            "prompt_injection": SignalType.PROMPT_INJECTION,
            "harmful_content": SignalType.HARMFUL_CONTENT,
        }
        return mapping.get(scanner_name, SignalType.ANOMALOUS_BEHAVIOR)

    @staticmethod
    def _map_severity(severity_str: str) -> SignalSeverity:
        """Map severity string to SignalSeverity."""
        mapping = {
            "critical": SignalSeverity.CRITICAL,
            "high": SignalSeverity.HIGH,
            "medium": SignalSeverity.MEDIUM,
            "low": SignalSeverity.LOW,
            "info": SignalSeverity.INFO,
        }
        return mapping.get(severity_str.lower(), SignalSeverity.MEDIUM)


class SecuritySignalManager:
    """
    Manages security signals for an application.

    Tracks signals, provides aggregation, and manages
    signal lifecycle.
    """

    def __init__(self, app_name: Optional[str] = None, max_signals: int = 1000):
        """
        Initialize the signal manager.

        Args:
            app_name: Application name (optional).
            max_signals: Maximum signals to keep in memory.
        """
        self.app_name = app_name or "default"
        self.max_signals = max_signals
        self._signals: list[SecuritySignal] = []
        self._signal_counts: dict[str, int] = {}

    def add_signal(self, signal: SecuritySignal) -> None:
        """
        Add a security signal.

        Args:
            signal: Signal to add.
        """
        self._signals.append(signal)

        # Update counts
        key = f"{signal.signal_type.value}:{signal.severity.value}"
        self._signal_counts[key] = self._signal_counts.get(key, 0) + 1

        # Trim if over limit
        if len(self._signals) > self.max_signals:
            # Remove oldest non-critical signals first
            self._trim_signals()

    def add_signals(self, signals: list[SecuritySignal]) -> None:
        """Add multiple signals."""
        for signal in signals:
            self.add_signal(signal)

    def _trim_signals(self) -> None:
        """Trim signals to stay under max limit."""
        # Keep critical signals, trim from oldest non-critical
        critical_signals = [
            s for s in self._signals if s.severity == SignalSeverity.CRITICAL
        ]
        other_signals = [
            s for s in self._signals if s.severity != SignalSeverity.CRITICAL
        ]

        # Sort by timestamp, keep newest
        other_signals.sort(key=lambda s: s.timestamp, reverse=True)

        keep_count = self.max_signals - len(critical_signals)
        other_signals = other_signals[:keep_count]

        self._signals = critical_signals + other_signals

    def get_signals(
        self,
        signal_type: Optional[SignalType] = None,
        severity: Optional[SignalSeverity] = None,
        node_name: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[SecuritySignal]:
        """
        Get signals with optional filtering.

        Args:
            signal_type: Filter by signal type.
            severity: Filter by severity.
            node_name: Filter by node name.
            since: Filter signals since timestamp.
            limit: Maximum signals to return.

        Returns:
            List of matching signals.
        """
        signals = self._signals

        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]

        if severity:
            signals = [s for s in signals if s.severity == severity]

        if node_name:
            signals = [s for s in signals if s.node_name == node_name]

        if since:
            signals = [s for s in signals if s.timestamp >= since]

        # Sort by timestamp descending (newest first)
        signals.sort(key=lambda s: s.timestamp, reverse=True)

        return signals[:limit]

    def get_critical_signals(self, limit: int = 50) -> list[SecuritySignal]:
        """Get critical severity signals."""
        return self.get_signals(severity=SignalSeverity.CRITICAL, limit=limit)

    def get_signal_counts(self) -> dict[str, int]:
        """Get counts of signals by type and severity."""
        return self._signal_counts.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of current signals."""
        severity_counts = {s.value: 0 for s in SignalSeverity}
        type_counts = {t.value: 0 for t in SignalType}

        for signal in self._signals:
            severity_counts[signal.severity.value] += 1
            type_counts[signal.signal_type.value] += 1

        return {
            "total_signals": len(self._signals),
            "by_severity": severity_counts,
            "by_type": type_counts,
            "unacknowledged": len([s for s in self._signals if not s.acknowledged]),
        }

    def create_signal(
        self,
        signal_type: str,
        severity: SignalSeverity,
        title: str,
        description: str,
        source_node: str,
        findings: list[dict[str, Any]],
    ) -> SecuritySignal:
        """
        Create a new security signal.

        Args:
            signal_type: Type of signal (string or SignalType).
            severity: Severity level.
            title: Signal title.
            description: Signal description.
            source_node: Node where signal originated.
            findings: List of findings.

        Returns:
            Created SecuritySignal.
        """
        # Convert string to SignalType if needed
        if isinstance(signal_type, str):
            try:
                signal_type_enum = SignalType(signal_type)
            except ValueError:
                signal_type_enum = SignalType.ANOMALOUS_BEHAVIOR
        else:
            signal_type_enum = signal_type

        signal = SecuritySignal(
            signal_type=signal_type_enum,
            severity=severity,
            message=description,
            title=title,
            description=description,
            source_node=source_node,
            node_name=source_node,
            findings=findings,
            status=SignalStatus.OPEN,
        )
        self.add_signal(signal)
        return signal

    def get_signal(self, signal_id: str) -> Optional[SecuritySignal]:
        """
        Get a signal by ID.

        Args:
            signal_id: Signal ID.

        Returns:
            SecuritySignal if found, None otherwise.
        """
        for signal in self._signals:
            if signal.signal_id == signal_id:
                return signal
        return None

    def update_status(self, signal_id: str, status: SignalStatus) -> bool:
        """
        Update the status of a signal.

        Args:
            signal_id: Signal ID.
            status: New status.

        Returns:
            True if signal was found and updated.
        """
        signal = self.get_signal(signal_id)
        if signal:
            signal.status = status
            return True
        return False

    def list_signals(
        self,
        status: Optional[SignalStatus] = None,
        severity: Optional[SignalSeverity] = None,
        limit: int = 100,
    ) -> list[SecuritySignal]:
        """
        List signals with optional filtering.

        Args:
            status: Filter by status.
            severity: Filter by severity.
            limit: Maximum signals to return.

        Returns:
            List of matching signals.
        """
        signals = self._signals

        if status:
            signals = [s for s in signals if s.status == status]

        if severity:
            signals = [s for s in signals if s.severity == severity]

        # Sort by timestamp descending (newest first)
        signals.sort(key=lambda s: s.timestamp, reverse=True)

        return signals[:limit]

    def acknowledge_signal(self, signal_id: str, user: Optional[str] = None) -> bool:
        """
        Acknowledge a signal.

        Args:
            signal_id: ID of signal to acknowledge.
            user: User who acknowledged (optional).

        Returns:
            True if signal was found and acknowledged.
        """
        signal = self.get_signal(signal_id)
        if signal:
            signal.acknowledged = True
            if user:
                signal.acknowledged_by = user
            return True
        return False

    def clear_acknowledged(self) -> int:
        """
        Clear acknowledged signals.

        Returns:
            Number of signals cleared.
        """
        initial_count = len(self._signals)
        self._signals = [s for s in self._signals if not s.acknowledged]
        return initial_count - len(self._signals)

    def clear_all(self) -> None:
        """Clear all signals."""
        self._signals.clear()
        self._signal_counts.clear()
