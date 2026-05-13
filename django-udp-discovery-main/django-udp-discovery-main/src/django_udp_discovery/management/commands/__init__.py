"""
Django management commands package for django-udp-discovery.

This package contains all management commands that can be executed via
Django's `manage.py` interface. These commands provide administrative
and debugging capabilities for the UDP discovery service.

Available Commands:
    start_discovery: Command to manually start the UDP discovery service
        with automatic cleanup and optional duration-based execution.

Usage:
    Management commands are invoked through Django's management interface::
    
        python manage.py <command_name> [options]
    
    For example::
    
        python manage.py start_discovery --duration 120

Note:
    All commands in this package extend Django's :class:`BaseCommand` class
    and follow Django's management command conventions.

See Also:
    :class:`django.core.management.base.BaseCommand`: Base class for
        Django management commands
"""

