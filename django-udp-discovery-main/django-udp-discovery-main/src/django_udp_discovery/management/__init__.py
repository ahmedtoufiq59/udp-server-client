"""
Django management commands module for django-udp-discovery.

This module provides Django management commands that allow manual control
over the UDP discovery service. Management commands are accessible via
Django's `manage.py` interface.

Available Commands:
    start_discovery: Start the UDP discovery service manually with optional
        duration-based auto-stop functionality.

Module Structure:
    commands/
        start_discovery.py: Management command for starting the UDP discovery
            service with automatic cleanup and duration control.

Example:
    To use the management commands, run them via Django's manage.py::
    
        python manage.py start_discovery
        python manage.py start_discovery --duration 60

See Also:
    :mod:`django_udp_discovery.listener`: Core UDP listener implementation
    :mod:`django_udp_discovery.conf`: Configuration management
"""

