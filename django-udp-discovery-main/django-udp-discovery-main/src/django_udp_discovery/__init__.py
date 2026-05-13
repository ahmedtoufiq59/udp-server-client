"""
Django UDP Discovery Package

A Django application that provides UDP-based service discovery functionality.
This package enables Django servers to automatically respond to discovery requests
from client nodes on a local network, allowing clients to find and connect to
the server without hardcoded IP addresses.

The package provides:
    - A threaded UDP listener that runs in the background
    - Automatic service startup when Django loads
    - Configurable discovery protocol settings
    - Thread-safe service management

Example:
    The service starts automatically when Django loads. To manually control it:

    >>> from django_udp_discovery import start_udp_service, stop_udp_service, is_running
    >>> start_udp_service()
    True
    >>> is_running()
    True
    >>> stop_udp_service()
    True

Attributes:
    __version__ (str): Package version number.
    default_app_config (str): Django app configuration class path for Django < 3.2.
"""

__version__: str = "1.0.0"
default_app_config: str = "django_udp_discovery.apps.UdpDiscoveryConfig"

# Export main functions
from django_udp_discovery.listener import start_udp_service, stop_udp_service, is_running

# Export utility functions for public API
from django_udp_discovery.utility import (
    get_server_ip,
    format_duration,
    is_port_in_use,
    validate_port,
    is_port_error,
)

__all__ = [
    'start_udp_service',
    'stop_udp_service',
    'is_running',
    'get_server_ip',
    'format_duration',
    'is_port_in_use',
    'validate_port',
    'is_port_error',
]