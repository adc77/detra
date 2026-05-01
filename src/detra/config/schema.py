"""Configuration schema using Pydantic models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BackendType(str, Enum):
    AUTO = "auto"
    CONSOLE = "console"
    OTEL = "otel"
    DATADOG = "datadog"


class JudgeProvider(str, Enum):
    NONE = "none"
    GEMINI = "gemini"
    LITELLM = "litellm"


# ---------------------------------------------------------------------------
# Component configs
# ---------------------------------------------------------------------------

class SamplingConfig(BaseModel):
    """Controls what fraction of requests get evaluated."""
    rate: float = Field(default=1.0, ge=0.0, le=1.0)
    always_sample_errors: bool = True
    always_sample_flagged: bool = True


class JudgeConfig(BaseModel):
    """Config for the pluggable LLM judge."""
    provider: JudgeProvider = JudgeProvider.NONE
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=16384)

    @model_validator(mode="after")
    def set_provider_default_model(self) -> "JudgeConfig":
        if self.provider == JudgeProvider.LITELLM and not self.model:
            self.model = "gpt-4o-mini"
        elif self.provider == JudgeProvider.GEMINI and not self.model:
            self.model = "gemini-2.5-flash"
        return self


class DatadogConfig(BaseModel):
    """Datadog connection -- fully optional in v0.2+."""
    api_key: str = Field(default="", description="Datadog API Key")
    app_key: str = Field(default="", description="Datadog Application Key")
    site: str = Field(default="datadoghq.com")
    service: Optional[str] = None
    env: Optional[str] = None
    version: Optional[str] = None
    verify_ssl: bool = True
    ssl_cert_path: Optional[str] = None


def _is_resolved_secret(value: Optional[str]) -> bool:
    return bool(value and not value.startswith("${"))


class GeminiConfig(BaseModel):
    """Gemini judge config (legacy -- prefer JudgeConfig for new setups)."""
    api_key: Optional[str] = Field(default=None, validate_default=True)
    project_id: Optional[str] = None
    location: str = "us-central1"
    model: str = Field(default="gemini-2.5-flash")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)

    @field_validator("api_key", mode="before")
    @classmethod
    def _resolve_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v
        import os
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


class NodeConfig(BaseModel):
    """Configuration for a traced node (function / workflow)."""
    description: str = ""
    expected_behaviors: list[str] = Field(default_factory=list)
    unexpected_behaviors: list[str] = Field(default_factory=list)
    adherence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    latency_warning_ms: int = Field(default=3000, ge=0)
    latency_critical_ms: int = Field(default=10000, ge=0)
    evaluation_prompts: dict[str, str] = Field(default_factory=dict)
    security_checks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_latency_thresholds(self) -> "NodeConfig":
        if self.latency_warning_ms > self.latency_critical_ms:
            raise ValueError("latency_warning_ms must be <= latency_critical_ms")
        return self


# ---------------------------------------------------------------------------
# Integration configs
# ---------------------------------------------------------------------------

class SlackConfig(BaseModel):
    enabled: bool = False
    webhook_url: Optional[str] = None
    channel: str = "#llm-alerts"
    notify_on: list[str] = Field(default_factory=lambda: ["flag_raised", "incident_created"])
    mention_on_critical: list[str] = Field(default_factory=list)


class PagerDutyConfig(BaseModel):
    enabled: bool = False
    integration_key: Optional[str] = None
    severity_mapping: dict[str, str] = Field(
        default_factory=lambda: {"critical": "critical", "warning": "warning", "info": "info"}
    )


class WebhookConfig(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["flag_raised"])
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 30


class IntegrationsConfig(BaseModel):
    slack: SlackConfig = Field(default_factory=SlackConfig)
    pagerduty: Optional[PagerDutyConfig] = Field(default_factory=PagerDutyConfig)
    webhooks: list[WebhookConfig] = Field(default_factory=list)

    @field_validator("pagerduty", mode="before")
    @classmethod
    def validate_pagerduty(cls, v: Any) -> Any:
        if v is None:
            return PagerDutyConfig()
        return v


class AlertConfig(BaseModel):
    name: str
    description: str = ""
    metric: str
    condition: str
    threshold: float
    window_minutes: int = 15
    severity: str = "warning"
    notify: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    pii_detection_enabled: bool = True
    pii_patterns: list[str] = Field(
        default_factory=lambda: ["email", "phone", "ssn", "credit_card", "ip_address"]
    )
    prompt_injection_detection: bool = True
    sensitive_topics: list[str] = Field(default_factory=list)
    block_on_detection: bool = False


class ThresholdsConfig(BaseModel):
    adherence_warning: float = 0.85
    adherence_critical: float = 0.70
    latency_warning_ms: int = 3000
    latency_critical_ms: int = 10000
    error_rate_warning: float = 0.05
    error_rate_critical: float = 0.15
    token_usage_warning: int = 10000
    token_usage_critical: int = 50000


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class DetraConfig(BaseModel):
    """Root configuration object for detra."""

    app_name: str
    version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT

    # v0.2 pluggable architecture
    backend: BackendType = BackendType.AUTO
    judge_config: JudgeConfig = Field(default_factory=JudgeConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)

    # Legacy / optional provider configs
    datadog: Optional[DatadogConfig] = Field(default_factory=DatadogConfig)
    gemini: Optional[GeminiConfig] = Field(default_factory=GeminiConfig)

    nodes: dict[str, NodeConfig] = Field(default_factory=dict)

    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    alerts: list[AlertConfig] = Field(default_factory=list)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)

    create_dashboard: bool = False
    dashboard_name: Optional[str] = None

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, v: str) -> str:
        v = v.lower().replace(" ", "-")
        if len(v) > 193:
            raise ValueError("app_name must be 193 characters or less")
        return v

    @model_validator(mode="after")
    def validate_explicit_backend(self) -> "DetraConfig":
        if self.backend == BackendType.DATADOG:
            if (
                not self.datadog
                or not _is_resolved_secret(self.datadog.api_key)
                or not _is_resolved_secret(self.datadog.app_key)
            ):
                raise ValueError("backend=datadog requires datadog.api_key and datadog.app_key")
        return self


# Backward compat aliases
detraConfig = DetraConfig


class DetraSettings(BaseSettings):
    """Environment-based settings that override YAML values."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    dd_api_key: Optional[str] = Field(default=None, alias="DD_API_KEY")
    dd_app_key: Optional[str] = Field(default=None, alias="DD_APP_KEY")
    dd_site: str = Field(default="datadoghq.com", alias="DD_SITE")

    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_cloud_project: Optional[str] = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field(default="us-central1", alias="GOOGLE_CLOUD_LOCATION")

    detra_app_name: str = Field(default="detra-app", alias="DETRA_APP_NAME")
    detra_env: str = Field(default="development", alias="DETRA_ENV")
    detra_eval_model: str = Field(default="gemini-2.5-flash", alias="DETRA_EVAL_MODEL")

    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    slack_channel: str = Field(default="#llm-alerts", alias="SLACK_CHANNEL")

# Backward compat alias
detraSettings = DetraSettings
