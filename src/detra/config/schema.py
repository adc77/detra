"""Configuration schema using Pydantic models."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EvalModel(str, Enum):
    """Supported Gemini models for evaluation."""
    GEMINI_MODEL = "gemini-2.5-flash"


class DatadogConfig(BaseModel):
    """Datadog connection configuration."""
    api_key: str = Field(..., description="Datadog API Key")
    app_key: str = Field(..., description="Datadog Application Key")
    site: str = Field(default="datadoghq.com", description="Datadog site")
    service: Optional[str] = None
    env: Optional[str] = None
    version: Optional[str] = None
    verify_ssl: bool = Field(
        default=True, description="Verify SSL certificates (set False for development only)"
    )
    ssl_cert_path: Optional[str] = Field(
        default=None, description="Path to SSL certificate bundle (uses certifi by default)"
    )


class GeminiConfig(BaseModel):
    """Gemini/Vertex AI configuration for evaluation."""
    api_key: Optional[str] = Field(default=None, description="Gemini API Key")
    project_id: Optional[str] = Field(default=None, description="GCP Project ID for Vertex AI")
    location: str = Field(default="us-central1", description="Vertex AI location")
    model: EvalModel = Field(default=EvalModel.GEMINI_MODEL)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class NodeConfig(BaseModel):
    """Configuration for a traced node (function/workflow)."""
    description: str = ""
    expected_behaviors: list[str] = Field(default_factory=list)
    unexpected_behaviors: list[str] = Field(default_factory=list)
    adherence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    latency_warning_ms: int = Field(default=3000)
    latency_critical_ms: int = Field(default=10000)
    evaluation_prompts: dict[str, str] = Field(default_factory=dict)
    security_checks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SlackConfig(BaseModel):
    """Slack integration configuration."""
    enabled: bool = False
    webhook_url: Optional[str] = None
    channel: str = "#llm-alerts"
    notify_on: list[str] = Field(default_factory=lambda: ["flag_raised", "incident_created"])
    mention_on_critical: list[str] = Field(default_factory=list)


class PagerDutyConfig(BaseModel):
    """PagerDuty integration configuration."""
    enabled: bool = False
    integration_key: Optional[str] = None
    severity_mapping: dict[str, str] = Field(
        default_factory=lambda: {
            "critical": "critical",
            "warning": "warning",
            "info": "info",
        }
    )


class WebhookConfig(BaseModel):
    """Custom webhook configuration."""
    url: str
    events: list[str] = Field(default_factory=lambda: ["flag_raised"])
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 30


class IntegrationsConfig(BaseModel):
    """External integrations configuration."""
    slack: SlackConfig = Field(default_factory=SlackConfig)
    pagerduty: Optional[PagerDutyConfig] = Field(default_factory=PagerDutyConfig)
    webhooks: list[WebhookConfig] = Field(default_factory=list)

    @field_validator("pagerduty", mode="before")
    @classmethod
    def validate_pagerduty(cls, v: Any) -> Any:
        """Handle None values for pagerduty config."""
        if v is None:
            return PagerDutyConfig()
        return v


class AlertConfig(BaseModel):
    """Custom alert/monitor configuration."""
    name: str
    description: str = ""
    metric: str
    condition: str  # gt, lt, gte, lte
    threshold: float
    window_minutes: int = 15
    severity: str = "warning"  # critical, warning, info
    notify: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    """Security scanning configuration."""
    pii_detection_enabled: bool = True
    pii_patterns: list[str] = Field(
        default_factory=lambda: ["email", "phone", "ssn", "credit_card", "ip_address"]
    )
    prompt_injection_detection: bool = True
    sensitive_topics: list[str] = Field(default_factory=list)
    block_on_detection: bool = False


class ThresholdsConfig(BaseModel):
    """Global threshold configuration."""
    adherence_warning: float = 0.85
    adherence_critical: float = 0.70
    latency_warning_ms: int = 3000
    latency_critical_ms: int = 10000
    error_rate_warning: float = 0.05
    error_rate_critical: float = 0.15
    token_usage_warning: int = 10000
    token_usage_critical: int = 50000


class detraConfig(BaseModel):
    """Main detra configuration."""
    app_name: str
    version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT

    datadog: DatadogConfig
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)

    nodes: dict[str, NodeConfig] = Field(default_factory=dict)

    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    alerts: list[AlertConfig] = Field(default_factory=list)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)

    create_dashboard: bool = True
    dashboard_name: Optional[str] = None

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, v: str) -> str:
        """Validate and normalize app name for Datadog ml_app naming requirements."""
        v = v.lower().replace(" ", "-")
        if len(v) > 193:
            raise ValueError("app_name must be 193 characters or less")
        return v


class detraSettings(BaseSettings):
    """Environment-based settings that override config file values."""

    dd_api_key: Optional[str] = Field(default=None, alias="DD_API_KEY")
    dd_app_key: Optional[str] = Field(default=None, alias="DD_APP_KEY")
    dd_site: str = Field(default="datadoghq.com", alias="DD_SITE")

    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_cloud_project: Optional[str] = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field(default="us-central1", alias="GOOGLE_CLOUD_LOCATION")

    detra_app_name: str = Field(default="detra-app", alias="detra_APP_NAME")
    detra_env: str = Field(default="development", alias="detra_ENV")
    detra_eval_model: str = Field(default="gemini-2.5-flash", alias="detra_EVAL_MODEL")

    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    slack_channel: str = Field(default="#llm-alerts", alias="SLACK_CHANNEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
