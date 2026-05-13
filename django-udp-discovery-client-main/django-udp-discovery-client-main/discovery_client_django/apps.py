"""
Django app configuration for discovery_client_django.
"""
from django.apps import AppConfig


class DiscoveryClientDjangoConfig(AppConfig):
    """App configuration for discovery_client_django."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'discovery_client_django'
    verbose_name = 'Django UDP Discovery Client'
