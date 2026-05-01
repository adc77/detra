"""Configuration loading and management."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

from detra.config.schema import (
    DetraConfig,
    DetraSettings,
    NodeConfig,
)

# Backward compat re-exports
detraConfig = DetraConfig
detraSettings = DetraSettings

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)}")


def load_yaml_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path) as f:
        config_data = yaml.safe_load(f)

    return _expand_env_vars(config_data or {})


def _expand_env_vars(obj: Any) -> Any:
    """Recursively expand ``${VAR}`` patterns -- works mid-string too."""
    if isinstance(obj, str):
        return _ENV_VAR_RE.sub(lambda m: os.getenv(m.group(1), m.group(0)), obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    config_path: str | None = None,
    env_file: str | None = None,
) -> DetraConfig:
    """Load config from YAML + env vars.  Env vars win on conflict."""

    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv()

    settings = DetraSettings()

    config_data: dict[str, Any] = {
        "app_name": settings.detra_app_name,
        "environment": settings.detra_env,
        "datadog": {
            "api_key": settings.dd_api_key or "",
            "app_key": settings.dd_app_key or "",
            "site": settings.dd_site,
        },
        "gemini": {
            "api_key": settings.google_api_key,
            "project_id": settings.google_cloud_project,
            "location": settings.google_cloud_location,
            "model": settings.detra_eval_model,
        },
        "integrations": {
            "slack": {
                "enabled": bool(settings.slack_webhook_url),
                "webhook_url": settings.slack_webhook_url,
                "channel": settings.slack_channel,
            }
        },
    }

    if config_path:
        yaml_config = load_yaml_config(config_path)
        config_data = _deep_merge(config_data, yaml_config)

    if settings.dd_api_key:
        config_data.setdefault("datadog", {})["api_key"] = settings.dd_api_key
    if settings.dd_app_key:
        config_data.setdefault("datadog", {})["app_key"] = settings.dd_app_key
    if settings.google_api_key:
        config_data.setdefault("gemini", {})["api_key"] = settings.google_api_key

    return DetraConfig(**config_data)


# ---------------------------------------------------------------------------
# Global config singleton
# ---------------------------------------------------------------------------

_config: Optional[DetraConfig] = None


def get_config() -> DetraConfig:
    if _config is None:
        raise RuntimeError("Configuration not loaded.  Call load_config() first.")
    return _config


def set_config(config: DetraConfig) -> None:
    global _config
    _config = config


def get_node_config(node_name: str) -> Optional[NodeConfig]:
    config = get_config()
    return config.nodes.get(node_name)


def reset_config() -> None:
    global _config
    _config = None
