"""
Configuration module for django-udp-discovery.

This module provides a settings wrapper that allows configuration of the UDP
discovery service through Django's settings system, with sensible defaults
as fallbacks. All settings can be overridden in the host project's settings.py.

The configuration system checks Django settings first, then falls back to
default values if a setting is not defined. This allows projects to customize
the discovery behavior without requiring all settings to be specified.

Available Settings:
    DISCOVERY_PORT (int): UDP port number for discovery service (default: 9999).
    DISCOVERY_MESSAGE (str): Message clients send to discover servers (default: "DISCOVER_SERVER").
    RESPONSE_PREFIX (str): Prefix for server response messages (default: "SERVER_IP:").
    DISCOVERY_TIMEOUT (float): Timeout in seconds for client discovery (default: 0.5).
    DISCOVERY_BUFFER_SIZE (int): UDP buffer size in bytes (default: 1024).
    ENABLE_LOGGING (bool): Enable/disable logging for discovery service (default: True).
    DISCOVERY_SECRET_KEY (str): Optional Fernet key for encrypted discovery (default: "").
        If empty, ``django_udp_discovery.crypto`` falls back to the ``DISCOVERY_SECRET_KEY``
        environment variable. Use a key from ``Fernet.generate_key()``; never commit real keys.
    DISCOVERY_ENCRYPTION_ENABLED (bool): When True, discovery requests and responses use
        Fernet (see ``django_udp_discovery.crypto``). Requires a valid ``DISCOVERY_SECRET_KEY``.
        Default: False (plain UDP, backward compatible).

Usage:
    Access settings directly as attributes:
        >>> from django_udp_discovery.conf import settings
        >>> port = settings.DISCOVERY_PORT
        >>> message = settings.DISCOVERY_MESSAGE
    
    Or use the safe getter method:
        >>> port = settings.get("DISCOVERY_PORT", default=8888)
    
    Override in Django settings.py:
        DISCOVERY_PORT = 7777
        DISCOVERY_MESSAGE = "FIND_SERVER"
"""

from typing import Any, Dict, Union
from django.conf import settings as django_settings


class _DiscoverySettings:
    """
    Settings wrapper class for UDP discovery configuration.
    
    This class provides a unified interface for accessing UDP discovery settings
    with automatic fallback to default values. It checks Django's settings first,
    then uses built-in defaults if a setting is not found.
    
    The class is designed to be used as a singleton through the module-level
    `settings` instance. Access settings as attributes or use the `get()` method
    for safe access with custom defaults.
    
    Attributes:
        DEFAULTS (dict): Dictionary of default setting values.
    
    Example:
        >>> from django_udp_discovery.conf import settings
        >>> # Access as attribute
        >>> port = settings.DISCOVERY_PORT
        >>> # Safe access with custom default
        >>> timeout = settings.get("DISCOVERY_TIMEOUT", default=1.0)
    """
    
    # Default configuration values
    DEFAULTS: Dict[str, Union[int, str, float, bool]] = {
        "DISCOVERY_PORT": 9999,
        "DISCOVERY_MESSAGE": "DISCOVER_SERVER",
        "RESPONSE_PREFIX": "SERVER_IP:",
        "DISCOVERY_TIMEOUT": 0.5,
        "DISCOVERY_BUFFER_SIZE": 1024,   # bytes
        "ENABLE_LOGGING": True,
        "DISCOVERY_SECRET_KEY": "",
        "DISCOVERY_ENCRYPTION_ENABLED": False,
    }

    def __getattr__(self, name: str) -> Union[int, str, float, bool]:
        """
        Retrieve a setting value with automatic fallback to defaults.
        
        This method is called when an attribute is accessed that doesn't exist
        as a class attribute. It first checks Django's settings, then falls back
        to the default values defined in DEFAULTS.
        
        Args:
            name (str): The name of the setting to retrieve.
        
        Returns:
            The setting value from Django settings or default values.
        
        Raises:
            AttributeError: If the setting name is not found in Django settings
                or in the default values dictionary.
        
        Example:
            >>> settings.DISCOVERY_PORT
            9999
            >>> settings.INVALID_SETTING
            AttributeError: Invalid discovery setting: 'INVALID_SETTING'
        """
        if hasattr(django_settings, name):
            return getattr(django_settings, name)

        if name in self.DEFAULTS:
            return self.DEFAULTS[name]

        raise AttributeError(f"Invalid discovery setting: '{name}'")

    def get(self, name: str, default: Any = None) -> Any:
        """
        Safely retrieve a setting value with optional custom default.
        
        This method provides a safe way to access settings with a custom default
        value. It first attempts to get the setting using the standard attribute
        access mechanism, then falls back to the provided default, and finally
        to the built-in default if available.
        
        Args:
            name (str): The name of the setting to retrieve.
            default (optional): Custom default value to use if setting is not found.
                If None, uses the built-in default from DEFAULTS if available.
        
        Returns:
            The setting value, or the provided/default fallback value.
        
        Example:
            >>> settings.get("DISCOVERY_PORT")
            9999
            >>> settings.get("DISCOVERY_PORT", default=8888)
            9999  # Returns actual setting, not default
            >>> settings.get("NON_EXISTENT", default="fallback")
            'fallback'
        """
        try:
            return getattr(self, name)
        except AttributeError:
            return default if default is not None else self.DEFAULTS.get(name)


# Expose as a singleton-style module object
settings = _DiscoverySettings()
