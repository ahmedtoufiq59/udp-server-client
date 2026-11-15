"""
Settings for running the django_udp_discovery test suite from the demo project:

    python manage.py test django_udp_discovery --settings=demo.test_settings

The tests turn encryption on and off per test, so this module keeps it off and
sets no keys, and needs no environment variables.
"""

SECRET_KEY = "test-only-not-secret"
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_udp_discovery",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DISCOVERY_ENCRYPTION_ENABLED = False
DISCOVERY_SECRET_KEY = ""
DISCOVERY_PREVIOUS_SECRET_KEYS = []
