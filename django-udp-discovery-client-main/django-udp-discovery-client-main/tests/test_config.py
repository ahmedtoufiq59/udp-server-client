"""
Tests for load_config() and ClientConfig.from_env().

Verify that environment variables (prefix DISCOVERY_CLIENT_) are applied
and that runtime kwargs override env vars and defaults.
"""
import os
import pytest
from discovery_client import load_config, ClientConfig


class TestLoadConfigEnvPriority:
    """load_config() must use env vars over defaults and kwargs over env."""

    def test_load_config_defaults_without_env(self):
        """With no env set, load_config() returns default values."""
        # Clear relevant env vars to avoid leakage from test environment
        env_keys = [
            "DISCOVERY_CLIENT_PORT", "DISCOVERY_CLIENT_MESSAGE",
            "DISCOVERY_CLIENT_RESPONSE_PREFIX", "DISCOVERY_CLIENT_TIMEOUT",
            "DISCOVERY_CLIENT_RETRIES", "DISCOVERY_CLIENT_ENABLE_SUBNET_SCAN",
            "DISCOVERY_CLIENT_INTERFACES_WHITELIST", "DISCOVERY_CLIENT_INTERFACES_BLACKLIST",
        ]
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        try:
            config = load_config()
            assert config.discovery_port == 9999
            assert config.discovery_message == b"DISCOVER_SERVER"
            assert config.response_prefix == b"SERVER_IP:"
            assert config.timeout == 5.0
            assert config.retries == 3
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_load_config_env_overrides_defaults(self):
        """Environment variables override default values."""
        os.environ["DISCOVERY_CLIENT_PORT"] = "8888"
        os.environ["DISCOVERY_CLIENT_TIMEOUT"] = "10.0"
        try:
            config = load_config()
            assert config.discovery_port == 8888
            assert config.timeout == 10.0
        finally:
            os.environ.pop("DISCOVERY_CLIENT_PORT", None)
            os.environ.pop("DISCOVERY_CLIENT_TIMEOUT", None)

    def test_load_config_kwargs_override_env(self):
        """Runtime kwargs take precedence over environment variables."""
        os.environ["DISCOVERY_CLIENT_PORT"] = "8888"
        os.environ["DISCOVERY_CLIENT_TIMEOUT"] = "10.0"
        try:
            config = load_config(discovery_port=7777, timeout=2.0)
            assert config.discovery_port == 7777
            assert config.timeout == 2.0
        finally:
            os.environ.pop("DISCOVERY_CLIENT_PORT", None)
            os.environ.pop("DISCOVERY_CLIENT_TIMEOUT", None)

    def test_load_config_env_message_and_prefix(self):
        """Env DISCOVERY_CLIENT_MESSAGE and RESPONSE_PREFIX are applied."""
        os.environ["DISCOVERY_CLIENT_MESSAGE"] = "PING"
        os.environ["DISCOVERY_CLIENT_RESPONSE_PREFIX"] = "PONG:"
        try:
            config = load_config()
            assert config.discovery_message == b"PING"
            assert config.response_prefix == b"PONG:"
        finally:
            os.environ.pop("DISCOVERY_CLIENT_MESSAGE", None)
            os.environ.pop("DISCOVERY_CLIENT_RESPONSE_PREFIX", None)

    def test_load_config_env_interfaces_list(self):
        """Env INTERFACES_WHITELIST and BLACKLIST are parsed as lists."""
        os.environ["DISCOVERY_CLIENT_INTERFACES_WHITELIST"] = "eth0, wlan0"
        os.environ["DISCOVERY_CLIENT_INTERFACES_BLACKLIST"] = "docker0"
        try:
            config = load_config()
            assert config.interfaces_whitelist == ["eth0", "wlan0"]
            assert config.interfaces_blacklist == ["docker0"]
        finally:
            os.environ.pop("DISCOVERY_CLIENT_INTERFACES_WHITELIST", None)
            os.environ.pop("DISCOVERY_CLIENT_INTERFACES_BLACKLIST", None)
