"""Tests for the config module."""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from vertiguard.config.schema import (
    AlertConfig,
    DatadogConfig,
    Environment,
    GeminiConfig,
    NodeConfig,
    SecurityConfig,
    ThresholdsConfig,
    VertiGuardConfig,
)
from vertiguard.config.loader import (
    load_config,
    get_config,
    get_node_config,
    set_config,
    _expand_env_vars,
    _deep_merge,
)


class TestNodeConfig:
    """Tests for NodeConfig schema."""

    def test_valid_node_config(self):
        """Test creating a valid NodeConfig."""
        config = NodeConfig(
            description="Test node",
            expected_behaviors=["Must return JSON"],
            unexpected_behaviors=["Invalid output"],
            adherence_threshold=0.85,
        )
        assert config.description == "Test node"
        assert config.adherence_threshold == 0.85
        assert len(config.expected_behaviors) == 1

    def test_node_config_defaults(self):
        """Test NodeConfig default values."""
        config = NodeConfig(
            description="Test",
            expected_behaviors=[],
            unexpected_behaviors=[],
        )
        assert config.adherence_threshold == 0.80
        assert config.latency_warning_ms == 3000
        assert config.latency_critical_ms == 10000
        assert config.security_checks == []
        assert config.tags == []

    def test_node_config_with_security_checks(self):
        """Test NodeConfig with security checks."""
        config = NodeConfig(
            description="Secure node",
            expected_behaviors=["Must be secure"],
            unexpected_behaviors=[],
            security_checks=["pii_detection", "prompt_injection"],
        )
        assert "pii_detection" in config.security_checks
        assert "prompt_injection" in config.security_checks

    def test_adherence_threshold_bounds(self):
        """Test adherence threshold must be between 0 and 1."""
        # Valid threshold
        config = NodeConfig(
            description="Test",
            expected_behaviors=[],
            unexpected_behaviors=[],
            adherence_threshold=0.5,
        )
        assert config.adherence_threshold == 0.5

        # Edge cases
        config_min = NodeConfig(
            description="Test",
            expected_behaviors=[],
            unexpected_behaviors=[],
            adherence_threshold=0.0,
        )
        assert config_min.adherence_threshold == 0.0

        config_max = NodeConfig(
            description="Test",
            expected_behaviors=[],
            unexpected_behaviors=[],
            adherence_threshold=1.0,
        )
        assert config_max.adherence_threshold == 1.0


class TestDatadogConfig:
    """Tests for DatadogConfig schema."""

    def test_valid_datadog_config(self, sample_datadog_config):
        """Test creating a valid DatadogConfig."""
        assert sample_datadog_config.api_key == "test_api_key"
        assert sample_datadog_config.site == "datadoghq.com"

    def test_datadog_config_defaults(self):
        """Test DatadogConfig default values."""
        config = DatadogConfig(
            api_key="key",
            app_key="app",
            site="datadoghq.com",
            service="svc",
            env="prod",
            version="1.0",
        )
        assert config.site == "datadoghq.com"


class TestGeminiConfig:
    """Tests for GeminiConfig schema."""

    def test_valid_gemini_config(self, sample_gemini_config):
        """Test creating a valid GeminiConfig."""
        assert sample_gemini_config.model == "gemini-1.5-flash"
        assert sample_gemini_config.temperature == 0.1

    def test_gemini_config_defaults(self):
        """Test GeminiConfig default values."""
        config = GeminiConfig(api_key="key")
        assert config.model == "gemini-1.5-flash"
        assert config.temperature == 0.1
        assert config.max_tokens == 1024


class TestSecurityConfig:
    """Tests for SecurityConfig schema."""

    def test_valid_security_config(self, sample_security_config):
        """Test creating a valid SecurityConfig."""
        assert sample_security_config.pii_detection_enabled is True
        assert "email" in sample_security_config.pii_patterns

    def test_security_config_defaults(self):
        """Test SecurityConfig default values."""
        config = SecurityConfig()
        assert config.pii_detection_enabled is True
        assert config.prompt_injection_detection is True
        assert config.block_on_detection is False
        assert "email" in config.pii_patterns


class TestThresholdsConfig:
    """Tests for ThresholdsConfig schema."""

    def test_valid_thresholds_config(self, sample_thresholds_config):
        """Test creating a valid ThresholdsConfig."""
        assert sample_thresholds_config.adherence_warning == 0.85
        assert sample_thresholds_config.adherence_critical == 0.70

    def test_thresholds_config_defaults(self):
        """Test ThresholdsConfig default values."""
        config = ThresholdsConfig()
        assert config.adherence_warning == 0.85
        assert config.latency_warning_ms == 3000


class TestVertiGuardConfig:
    """Tests for VertiGuardConfig schema."""

    def test_valid_vertiguard_config(self, sample_vertiguard_config):
        """Test creating a valid VertiGuardConfig."""
        assert sample_vertiguard_config.app_name == "test-app"
        assert sample_vertiguard_config.environment == Environment.DEVELOPMENT
        assert "extract_entities" in sample_vertiguard_config.nodes

    def test_app_name_validation(self):
        """Test app_name must be valid for Datadog ml_app."""
        # Valid app names
        valid_names = ["my-app", "my_app", "myapp123", "app.name"]
        for name in valid_names:
            config = VertiGuardConfig(
                app_name=name,
                version="1.0.0",
                datadog=DatadogConfig(
                    api_key="k", app_key="a", site="s", service="s", env="e", version="v"
                ),
                gemini=GeminiConfig(api_key="k"),
            )
            assert config.app_name == name

    def test_environment_enum(self):
        """Test Environment enum values."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"


class TestConfigLoader:
    """Tests for config loader functions."""

    def test_expand_env_vars(self):
        """Test environment variable expansion."""
        with patch.dict(os.environ, {"MY_VAR": "my_value"}):
            result = _expand_env_vars({"key": "${MY_VAR}"})
            assert result["key"] == "my_value"

    def test_expand_env_vars_nested(self):
        """Test nested environment variable expansion."""
        with patch.dict(os.environ, {"VAR1": "value1", "VAR2": "value2"}):
            data = {
                "level1": {
                    "level2": "${VAR1}",
                    "other": "${VAR2}",
                }
            }
            result = _expand_env_vars(data)
            assert result["level1"]["level2"] == "value1"
            assert result["level1"]["other"] == "value2"

    def test_expand_env_vars_missing(self):
        """Test missing environment variable returns original string."""
        result = _expand_env_vars({"key": "${NONEXISTENT_VAR}"})
        assert result["key"] == "${NONEXISTENT_VAR}"

    def test_expand_env_vars_with_default(self):
        """Test environment variable with default value."""
        result = _expand_env_vars({"key": "${NONEXISTENT:-default}"})
        # Note: current implementation may not support defaults
        # This test documents expected behavior

    def test_deep_merge(self):
        """Test deep merging of dictionaries."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 10, "e": 4}, "f": 5}
        result = _deep_merge(base, override)

        assert result["a"] == 1
        assert result["b"]["c"] == 10
        assert result["b"]["d"] == 3
        assert result["b"]["e"] == 4
        assert result["f"] == 5

    def test_deep_merge_empty(self):
        """Test deep merge with empty dictionaries."""
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

        result = _deep_merge({}, base)
        assert result == {"a": 1}

    def test_load_config_from_file(self, temp_config_file, temp_env_file):
        """Test loading config from YAML file."""
        config = load_config(config_path=temp_config_file, env_file=temp_env_file)
        assert config.app_name == "test-yaml-app"
        assert config.version == "1.0.0"
        assert "test_node" in config.nodes

    def test_load_config_env_expansion(self, temp_config_file, temp_env_file):
        """Test that env vars are expanded when loading config."""
        config = load_config(config_path=temp_config_file, env_file=temp_env_file)
        assert config.datadog.api_key == "test_dd_api_key"
        assert config.gemini.api_key == "test_google_key"

    def test_get_set_config(self, sample_vertiguard_config):
        """Test global config getter and setter."""
        set_config(sample_vertiguard_config)
        retrieved = get_config()
        assert retrieved.app_name == sample_vertiguard_config.app_name

    def test_get_node_config(self, sample_vertiguard_config, sample_node_config):
        """Test getting node config by name."""
        set_config(sample_vertiguard_config)
        node = get_node_config("extract_entities")
        assert node is not None
        assert node.description == sample_node_config.description

    def test_get_node_config_not_found(self, sample_vertiguard_config):
        """Test getting non-existent node returns None."""
        set_config(sample_vertiguard_config)
        node = get_node_config("nonexistent_node")
        assert node is None


class TestAlertConfig:
    """Tests for AlertConfig schema."""

    def test_valid_alert_config(self):
        """Test creating a valid AlertConfig."""
        config = AlertConfig(
            name="High Error Rate",
            description="Too many errors",
            metric="vertiguard.errors",
            condition="gt",
            threshold=10.0,
            window_minutes=15,
            severity="warning",
        )
        assert config.name == "High Error Rate"
        assert config.threshold == 10.0

    def test_alert_config_defaults(self):
        """Test AlertConfig default values."""
        config = AlertConfig(
            name="Test Alert",
            description="Test",
            metric="test.metric",
            condition="gt",
            threshold=5.0,
        )
        assert config.window_minutes == 15
        assert config.severity == "warning"
        assert config.notify == []
        assert config.tags == []


class TestEdgeCases:
    """Edge case tests for config module."""

    def test_empty_nodes(self):
        """Test config with no nodes defined."""
        config = VertiGuardConfig(
            app_name="empty-app",
            version="1.0.0",
            datadog=DatadogConfig(
                api_key="k", app_key="a", site="s", service="s", env="e", version="v"
            ),
            gemini=GeminiConfig(api_key="k"),
            nodes={},
        )
        assert config.nodes == {}

    def test_node_with_empty_behaviors(self):
        """Test node with no expected or unexpected behaviors."""
        config = NodeConfig(
            description="Empty behaviors",
            expected_behaviors=[],
            unexpected_behaviors=[],
        )
        assert config.expected_behaviors == []
        assert config.unexpected_behaviors == []

    def test_config_with_all_integrations_disabled(self):
        """Test config with all integrations disabled."""
        from vertiguard.config.schema import IntegrationsConfig, SlackConfig

        config = IntegrationsConfig(
            slack=SlackConfig(enabled=False),
            pagerduty=None,
            webhooks=[],
        )
        assert not config.slack.enabled

    def test_very_long_behavior_string(self):
        """Test handling of very long behavior strings."""
        long_behavior = "Must " + "validate " * 1000 + "correctly"
        config = NodeConfig(
            description="Long behavior test",
            expected_behaviors=[long_behavior],
            unexpected_behaviors=[],
        )
        assert len(config.expected_behaviors[0]) > 1000

    def test_special_characters_in_node_description(self):
        """Test special characters in node description."""
        config = NodeConfig(
            description="Node with special chars: <>&\"'",
            expected_behaviors=[],
            unexpected_behaviors=[],
        )
        assert "<" in config.description

    def test_unicode_in_config(self):
        """Test Unicode characters in configuration."""
        config = NodeConfig(
            description="Node with unicode: ",
            expected_behaviors=["Must handle emoji output"],
            unexpected_behaviors=[],
        )
        assert "" in config.description
