"""Configuration loading and management."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

from detra.config.schema import (
    NodeConfig,
    VertiGuardConfig,
    VertiGuardSettings,
)


def load_yaml_config(config_path: str) -> dict[str, Any]:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path) as f:
        config_data = yaml.safe_load(f)

    return _expand_env_vars(config_data or {})


def _expand_env_vars(obj: Any) -> Any:
    """
    Recursively expand ${VAR} patterns in configuration values.

    Args:
        obj: Configuration object (dict, list, or scalar).

    Returns:
        Object with environment variables expanded.
    """
    if isinstance(obj, str):
        if obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.getenv(var_name, obj)
        return obj
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary.
        override: Override dictionary.

    Returns:
        Merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    config_path: Optional[str] = None,
    env_file: Optional[str] = None,
) -> VertiGuardConfig:
    """
    Load configuration from YAML file and environment variables.

    Environment variables take precedence over file values.

    Args:
        config_path: Path to vertiguard.yaml config file.
        env_file: Path to .env file (optional).

    Returns:
        Validated VertiGuardConfig instance.
    """
    # Load .env file
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Load environment settings
    settings = VertiGuardSettings()

    # Start with defaults from environment
    config_data: dict[str, Any] = {
        "app_name": settings.vertiguard_app_name,
        "environment": settings.vertiguard_env,
        "datadog": {
            "api_key": settings.dd_api_key or "",
            "app_key": settings.dd_app_key or "",
            "site": settings.dd_site,
        },
        "gemini": {
            "api_key": settings.google_api_key,
            "project_id": settings.google_cloud_project,
            "location": settings.google_cloud_location,
            "model": settings.vertiguard_eval_model,
        },
        "integrations": {
            "slack": {
                "enabled": bool(settings.slack_webhook_url),
                "webhook_url": settings.slack_webhook_url,
                "channel": settings.slack_channel,
            }
        },
    }

    # Merge with YAML config if provided
    if config_path:
        yaml_config = load_yaml_config(config_path)
        config_data = _deep_merge(config_data, yaml_config)

    # Override with any explicit environment variables (highest priority)
    if settings.dd_api_key:
        config_data["datadog"]["api_key"] = settings.dd_api_key
    if settings.dd_app_key:
        config_data["datadog"]["app_key"] = settings.dd_app_key
    if settings.google_api_key:
        config_data["gemini"]["api_key"] = settings.google_api_key

    return VertiGuardConfig(**config_data)


# Global config singleton
_config: Optional[VertiGuardConfig] = None


def get_config() -> VertiGuardConfig:
    """
    Get the global configuration.

    Returns:
        The current VertiGuardConfig instance.

    Raises:
        RuntimeError: If configuration hasn't been loaded.
    """
    global _config
    if _config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return _config


def set_config(config: VertiGuardConfig) -> None:
    """
    Set the global configuration.

    Args:
        config: VertiGuardConfig instance to set as global.
    """
    global _config
    _config = config


def get_node_config(node_name: str) -> Optional[NodeConfig]:
    """
    Get configuration for a specific node.

    Args:
        node_name: Name of the node to get config for.

    Returns:
        NodeConfig if found, None otherwise.
    """
    config = get_config()
    return config.nodes.get(node_name)


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
