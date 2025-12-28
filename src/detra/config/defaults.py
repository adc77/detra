"""Default configuration values for detra."""

from typing import Any

# Default threshold values
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "adherence_warning": 0.85,
    "adherence_critical": 0.70,
    "latency_warning_ms": 3000,
    "latency_critical_ms": 10000,
    "error_rate_warning": 0.05,
    "error_rate_critical": 0.15,
    "token_usage_warning": 10000,
    "token_usage_critical": 50000,
}

# Default security configuration
DEFAULT_SECURITY_CONFIG: dict[str, Any] = {
    "pii_detection_enabled": True,
    "pii_patterns": ["email", "phone", "ssn", "credit_card", "ip_address"],
    "prompt_injection_detection": True,
    "sensitive_topics": [],
    "block_on_detection": False,
}

# Default node configuration template
DEFAULT_NODE_CONFIG: dict[str, Any] = {
    "description": "",
    "expected_behaviors": [],
    "unexpected_behaviors": [],
    "adherence_threshold": 0.85,
    "latency_warning_ms": 3000,
    "latency_critical_ms": 10000,
    "evaluation_prompts": {},
    "security_checks": ["pii_detection", "prompt_injection"],
    "tags": [],
}

# Default Gemini configuration
DEFAULT_GEMINI_CONFIG: dict[str, Any] = {
    "model": "gemini-2.5-flash",
    "temperature": 0.1,
    "max_tokens": 1024,
    "location": "us-central1",
}

# Supported security check types
SECURITY_CHECK_TYPES: list[str] = [
    "pii_detection",
    "prompt_injection",
    "jailbreak_attempt",
    "sensitive_data_leak",
    "harmful_content",
]

# PII pattern names and their descriptions
PII_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "ssn": r"\d{3}[-\s]?\d{2}[-\s]?\d{4}",
    "credit_card": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
    "ip_address": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
}

# Flag categories for classification
FLAG_CATEGORIES: list[str] = [
    "hallucination",
    "format_error",
    "missing_content",
    "semantic_drift",
    "instruction_violation",
    "safety_violation",
    "context_loss",
    "reasoning_error",
    "security_violation",
    "unclassified",
]

# Severity levels
SEVERITY_LEVELS: list[str] = ["critical", "high", "medium", "low", "info"]

# Monitor types
MONITOR_TYPES: list[str] = [
    "adherence_warning",
    "adherence_critical",
    "flag_rate",
    "latency_warning",
    "latency_critical",
    "error_rate",
    "security_issues",
    "token_usage",
]
