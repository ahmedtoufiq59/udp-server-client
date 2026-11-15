"""
Django App Configuration for UDP Discovery

This module defines the Django application configuration for django-udp-discovery.
It automatically starts the UDP discovery service when Django is ready, unless
running in a test environment.

The app configuration ensures the UDP listener is initialized and running
whenever Django starts, providing seamless service discovery functionality.
"""

import atexit
import os
import sys
from typing import List, Optional

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
        It starts the UDP discovery listener when :func:`should_autostart` allows
        it: not during tests, not for management commands other than
        ``runserver``, only in runserver's serving (reloader child) process, and
        never when ``DISCOVERY_AUTOSTART = False``.
        
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
        if not should_autostart():
            return

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


#: Management commands that serve the site and should run the listener.
_SERVING_COMMANDS = {"runserver"}


def _management_command(argv: List[str]) -> Optional[str]:
    """
    Return the management command name if this process is ``manage.py <cmd>``,
    ``django-admin <cmd>`` or ``python -m django <cmd>``; otherwise ``None``.
    """
    if not argv:
        return None
    script = os.path.basename(argv[0])
    parent = os.path.basename(os.path.dirname(argv[0]))
    is_manage = (
        script in ("manage.py", "django-admin", "django-admin.py", "django-admin.exe")
        or (script == "__main__.py" and parent == "django")
    )
    if not is_manage:
        return None
    return argv[1] if len(argv) > 1 else ""


def should_autostart(argv: Optional[List[str]] = None, environ: Optional[dict] = None) -> bool:
    """
    Decide whether this process should start the UDP listener automatically.

    * ``DISCOVERY_AUTOSTART = False`` disables auto-start entirely.
    * Never during tests (``test`` command, pytest, or ``TESTING = True``).
    * For management commands, only ``runserver``. Other commands such as
      ``migrate``, ``shell`` or ``start_discovery`` (which starts its own listener)
      do not auto-start, so they don't fight a running server for the port.
    * Under ``runserver`` with the auto-reloader, only the child process that
      actually serves requests (``RUN_MAIN=true``) starts it; ``--noreload`` starts
      it directly.
    * Any other process (gunicorn, uvicorn, daphne, mod_wsgi, ...) auto-starts.
    """
    from django.conf import settings as django_settings

    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ

    if not getattr(django_settings, "DISCOVERY_AUTOSTART", True):
        return False

    is_testing = (
        "test" in argv
        or "pytest" in sys.modules
        or bool(getattr(django_settings, "TESTING", False))
    )
    if is_testing:
        return False

    command = _management_command(argv)
    if command is None:
        return True
    if command not in _SERVING_COMMANDS:
        return False
    if "--noreload" in argv:
        return True
    return environ.get("RUN_MAIN") == "true"
