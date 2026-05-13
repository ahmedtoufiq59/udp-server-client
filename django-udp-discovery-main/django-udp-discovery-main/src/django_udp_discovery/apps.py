"""
Django App Configuration for UDP Discovery

This module defines the Django application configuration for django-udp-discovery.
It automatically starts the UDP discovery service when Django is ready, unless
running in a test environment.

The app configuration ensures the UDP listener is initialized and running
whenever Django starts, providing seamless service discovery functionality.
"""

import atexit

from django.apps import AppConfig


class UdpDiscoveryConfig(AppConfig):
    """
    Django application configuration for django-udp-discovery.
    
    This configuration class automatically starts the UDP discovery service
    when Django is ready. The service runs in a background daemon thread
    and responds to discovery requests from client nodes.
    
    The service is automatically disabled during test runs to prevent port
    conflicts and ensure clean test execution.
    
    Attributes:
        default_auto_field (str): Default primary key field type for models.
        name (str): Full Python path to the application.
    """
    
    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'django_udp_discovery'

    def ready(self) -> None:
        """
        Initialize the UDP discovery service when Django is ready.
        
        This method is called by Django when the application is fully loaded.
        It automatically starts the UDP discovery listener unless the application
        is running in a test environment. Test detection checks for:
            - 'test' in sys.argv (Django test command)
            - 'pytest' in sys.modules (pytest framework)
            - TESTING setting in Django settings
        
        The service starts in a daemon thread, so it won't prevent Django
        from shutting down gracefully. An atexit handler is registered to
        ensure the service is properly stopped when the process exits.
        
        Note:
            This method may be called multiple times during Django startup
            in some configurations. The start_udp_service() function handles
            duplicate start attempts gracefully.
        
        Raises:
            OSError: If the configured UDP port is already in use.
        """
        # Only start in non-testing environments to avoid conflicts
        import sys
        from django.conf import settings as django_settings
        
        # Check if we're in a test environment
        is_testing = (
            'test' in sys.argv or
            'pytest' in sys.modules or
            hasattr(django_settings, 'TESTING') and django_settings.TESTING
        )
        
        if not is_testing:
            from django_udp_discovery.listener import start_udp_service, stop_udp_service, is_running
            
            # Register cleanup function to be called on process exit
            # This ensures the UDP service is properly stopped when Django shuts down
            # Only register once to avoid duplicate registrations
            if not hasattr(UdpDiscoveryConfig, '_atexit_registered'):
                atexit.register(stop_udp_service)
                UdpDiscoveryConfig._atexit_registered = True
            
            # Only auto-start if not already running (e.g., if started manually via command)
            if not is_running():
                start_udp_service()