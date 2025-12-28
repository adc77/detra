"""Security scanning utilities for detecting sensitive content."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ScanSeverity(str, Enum):
    """Severity levels for scan findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ScanResult:
    """Result of a security scan."""
    scanner_name: str
    detected: bool
    severity: ScanSeverity
    findings: list[dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None

    @property
    def finding_count(self) -> int:
        """Get count of findings."""
        return len(self.findings)


class SecurityScanner(ABC):
    """Base class for security scanners."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Scanner name."""
        pass

    @abstractmethod
    def scan(self, text: str) -> ScanResult:
        """
        Scan text for security issues.

        Args:
            text: Text to scan.

        Returns:
            ScanResult with findings.
        """
        pass

    def scan_input_output(
        self, input_text: str, output_text: str
    ) -> tuple[ScanResult, ScanResult]:
        """
        Scan both input and output.

        Args:
            input_text: Input text.
            output_text: Output text.

        Returns:
            Tuple of (input_result, output_result).
        """
        return self.scan(input_text), self.scan(output_text)


class PIIScanner(SecurityScanner):
    """Scanner for detecting personally identifiable information."""

    # PII patterns with severity
    PII_PATTERNS = {
        "email": {
            "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "severity": ScanSeverity.MEDIUM,
            "description": "Email address",
        },
        "phone": {
            "pattern": r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            "severity": ScanSeverity.MEDIUM,
            "description": "Phone number",
        },
        "ssn": {
            "pattern": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
            "severity": ScanSeverity.CRITICAL,
            "description": "Social Security Number",
        },
        "credit_card": {
            "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "severity": ScanSeverity.CRITICAL,
            "description": "Credit card number",
        },
        "ip_address": {
            "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "severity": ScanSeverity.LOW,
            "description": "IP address",
        },
        "date_of_birth": {
            "pattern": r"\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b",
            "severity": ScanSeverity.MEDIUM,
            "description": "Date of birth",
        },
        "passport": {
            "pattern": r"\b[A-Z]{1,2}\d{6,9}\b",
            "severity": ScanSeverity.HIGH,
            "description": "Passport number",
        },
    }

    def __init__(self, enabled_patterns: Optional[list[str]] = None):
        """
        Initialize the PII scanner.

        Args:
            enabled_patterns: List of pattern names to enable. If None, all are enabled.
                             If empty list [], no patterns are enabled.
        """
        if enabled_patterns is None:
            self.enabled_patterns = list(self.PII_PATTERNS.keys())
        else:
            self.enabled_patterns = enabled_patterns

    @property
    def name(self) -> str:
        return "pii_detection"

    def scan(self, text: str) -> ScanResult:
        """Scan text for PII."""
        findings = []
        max_severity = ScanSeverity.INFO

        # If no patterns enabled, return empty result
        if not self.enabled_patterns:
            return ScanResult(
                scanner_name=self.name,
                detected=False,
                severity=ScanSeverity.INFO,
                findings=[],
                summary=None,
            )

        for pattern_name in self.enabled_patterns:
            if pattern_name not in self.PII_PATTERNS:
                continue

            pattern_info = self.PII_PATTERNS[pattern_name]
            matches = re.findall(pattern_info["pattern"], text, re.IGNORECASE)

            for match in matches:
                # Store original value for testing/debugging, redact for evidence
                original_value = match if isinstance(match, str) else str(match)
                redacted = self._redact(original_value)

                findings.append({
                    "type": pattern_name,
                    "description": pattern_info["description"],
                    "severity": pattern_info["severity"].value,
                    "evidence": redacted,
                    "value": original_value,  # Store original for testing
                })

                if self._severity_order(pattern_info["severity"]) > self._severity_order(max_severity):
                    max_severity = pattern_info["severity"]

        return ScanResult(
            scanner_name=self.name,
            detected=len(findings) > 0,
            severity=max_severity if findings else ScanSeverity.INFO,
            findings=findings,
            summary=f"Found {len(findings)} PII instances" if findings else None,
        )

    def _redact(self, text: str, visible_chars: int = 4) -> str:
        """Redact sensitive text, keeping only some visible characters."""
        if len(text) <= visible_chars * 2:
            return "*" * len(text)
        return text[:visible_chars] + "*" * (len(text) - visible_chars * 2) + text[-visible_chars:]

    def _severity_order(self, severity: ScanSeverity) -> int:
        """Get numeric order for severity comparison."""
        order = {
            ScanSeverity.INFO: 0,
            ScanSeverity.LOW: 1,
            ScanSeverity.MEDIUM: 2,
            ScanSeverity.HIGH: 3,
            ScanSeverity.CRITICAL: 4,
        }
        return order.get(severity, 0)


class PromptInjectionScanner(SecurityScanner):
    """Scanner for detecting prompt injection attempts."""

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        # Instruction override attempts
        (r"ignore (?:all |any )?(?:previous|above|prior) (?:instructions?|prompts?)", ScanSeverity.HIGH),
        (r"disregard (?:all |any )?(?:previous|above|prior|your (?:training|instructions?|prompts?))", ScanSeverity.HIGH),
        (r"forget (?:everything|all|what)", ScanSeverity.HIGH),

        # Role manipulation
        (r"you are now", ScanSeverity.MEDIUM),
        (r"pretend (?:you are|to be)", ScanSeverity.MEDIUM),
        (r"act as (?:if you are|a)", ScanSeverity.MEDIUM),
        (r"roleplay as", ScanSeverity.MEDIUM),

        # System prompt extraction
        (r"(?:show|reveal|display|print|output) (?:your |the )?(?:system |initial )?(?:prompt|instructions)", ScanSeverity.HIGH),
        (r"what (?:are|were) your (?:initial |original )?instructions", ScanSeverity.HIGH),

        # Jailbreak attempts
        (r"DAN mode", ScanSeverity.CRITICAL),
        (r"jailbreak", ScanSeverity.CRITICAL),
        (r"developer mode", ScanSeverity.HIGH),
        (r"bypass (?:your |any )?(?:restrictions|limitations|safety|filters)", ScanSeverity.CRITICAL),

        # Delimiter injection
        (r"```(?:system|assistant|user)", ScanSeverity.MEDIUM),
        (r"\[INST\]|\[/INST\]", ScanSeverity.MEDIUM),
        (r"<\|(?:im_start|im_end|system|user|assistant)\|>", ScanSeverity.HIGH),
    ]

    @property
    def name(self) -> str:
        return "prompt_injection"

    def scan(self, text: str) -> ScanResult:
        """Scan text for prompt injection attempts."""
        findings = []
        max_severity = ScanSeverity.INFO

        for pattern, severity in self.INJECTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)

            for match in matches:
                findings.append({
                    "type": "prompt_injection",
                    "pattern": pattern[:50],
                    "severity": severity.value,
                    "evidence": match if isinstance(match, str) else str(match),
                })

                if self._severity_order(severity) > self._severity_order(max_severity):
                    max_severity = severity

        return ScanResult(
            scanner_name=self.name,
            detected=len(findings) > 0,
            severity=max_severity if findings else ScanSeverity.INFO,
            findings=findings,
            summary=f"Found {len(findings)} injection attempts" if findings else None,
        )

    def _severity_order(self, severity: ScanSeverity) -> int:
        """Get numeric order for severity comparison."""
        order = {
            ScanSeverity.INFO: 0,
            ScanSeverity.LOW: 1,
            ScanSeverity.MEDIUM: 2,
            ScanSeverity.HIGH: 3,
            ScanSeverity.CRITICAL: 4,
        }
        return order.get(severity, 0)


class ContentScanner(SecurityScanner):
    """Scanner for detecting harmful or sensitive content."""

    # Default content patterns to check
    DEFAULT_PATTERNS = {
        "violence": {
            "keywords": ["kill", "murder", "attack", "harm", "hurt", "weapon"],
            "severity": ScanSeverity.HIGH,
        },
        "illegal_activity": {
            "keywords": ["illegal", "hack", "steal", "fraud", "exploit"],
            "severity": ScanSeverity.HIGH,
        },
        "explicit": {
            "keywords": [],  # Would need more sophisticated detection
            "severity": ScanSeverity.MEDIUM,
        },
    }

    # Topic-based patterns
    TOPIC_PATTERNS = {
        "medical_records": {
            "keywords": ["diagnosis", "patient", "medical record", "treatment", "prescription", "symptoms"],
            "severity": ScanSeverity.HIGH,
        },
        "financial_details": {
            "keywords": ["account balance", "credit card", "bank account", "ssn", "social security"],
            "severity": ScanSeverity.CRITICAL,
        },
        "legal_advice": {
            "keywords": ["legal opinion", "you should sue", "file a lawsuit", "legal action"],
            "severity": ScanSeverity.MEDIUM,
        },
    }

    def __init__(self, sensitive_topics: Optional[list[str]] = None):
        """
        Initialize the content scanner.

        Args:
            sensitive_topics: List of sensitive topic names to scan for.
                             If None or empty, uses default patterns only.
        """
        self.sensitive_topics = sensitive_topics or []
        self._build_patterns()

    def _build_patterns(self):
        """Build the content patterns based on sensitive topics."""
        self.CONTENT_PATTERNS = self.DEFAULT_PATTERNS.copy()
        
        # Add topic-specific patterns if requested
        for topic in self.sensitive_topics:
            if topic in self.TOPIC_PATTERNS:
                self.CONTENT_PATTERNS[topic] = self.TOPIC_PATTERNS[topic]

    @property
    def name(self) -> str:
        return "harmful_content"

    def scan(self, text: str) -> ScanResult:
        """Scan text for harmful content."""
        findings = []
        text_lower = text.lower()

        # Only scan if we have patterns configured
        if not self.CONTENT_PATTERNS:
            return ScanResult(
                scanner_name=self.name,
                detected=False,
                severity=ScanSeverity.INFO,
                findings=[],
                summary=None,
            )

        for category, config in self.CONTENT_PATTERNS.items():
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    # Find context around keyword
                    idx = text_lower.find(keyword)
                    context_start = max(0, idx - 20)
                    context_end = min(len(text), idx + len(keyword) + 20)
                    context = text[context_start:context_end]

                    findings.append({
                        "type": category,
                        "keyword": keyword,
                        "severity": config["severity"].value,
                        "context": f"...{context}...",
                    })

        max_severity = ScanSeverity.INFO
        if findings:
            severities = [ScanSeverity(f["severity"]) for f in findings]
            max_severity = max(severities, key=lambda s: self._severity_order(s))

        return ScanResult(
            scanner_name=self.name,
            detected=len(findings) > 0,
            severity=max_severity,
            findings=findings,
            summary=f"Found {len(findings)} content concerns" if findings else None,
        )

    def _severity_order(self, severity: ScanSeverity) -> int:
        """Get numeric order for severity comparison."""
        order = {
            ScanSeverity.INFO: 0,
            ScanSeverity.LOW: 1,
            ScanSeverity.MEDIUM: 2,
            ScanSeverity.HIGH: 3,
            ScanSeverity.CRITICAL: 4,
        }
        return order.get(severity, 0)


class CompositeScan:
    """Runs multiple scanners and aggregates results."""

    def __init__(self, scanners: Optional[list[SecurityScanner]] = None):
        """
        Initialize with scanners.

        Args:
            scanners: List of scanners to use. Defaults to all standard scanners.
        """
        self.scanners = scanners or [
            PIIScanner(),
            PromptInjectionScanner(),
            ContentScanner(),
        ]

    def scan(self, text: str) -> list[ScanResult]:
        """Run all scanners on text."""
        return [scanner.scan(text) for scanner in self.scanners]

    def scan_all(self, text: str) -> dict[str, ScanResult]:
        """Run all scanners and return results by scanner name."""
        return {scanner.name: scanner.scan(text) for scanner in self.scanners}

    @property
    def scanner_names(self) -> list[str]:
        """Get list of scanner names."""
        return [s.name for s in self.scanners]
