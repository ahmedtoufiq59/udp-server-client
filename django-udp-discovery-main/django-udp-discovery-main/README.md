# django-udp-discovery

A Django application that provides UDP-based service discovery functionality, allowing clients on a local network to automatically discover and connect to Django servers without hardcoded IP addresses.

## Features

- **Automatic Service Discovery**: Django servers automatically respond to UDP discovery requests
- **Zero Configuration**: Works out of the box with sensible defaults
- **Thread-Safe**: Background daemon thread that doesn't block Django
- **Configurable**: All settings can be customized via Django settings
- **Production Ready**: Comprehensive error handling and graceful shutdown
- **Well Tested**: Full test coverage with isolated test cases

## Platform Support

⚠️ **Important**: The current version of `django-udp-discovery` is **not supported on macOS**. This package is designed for Windows and Linux environments. If you need macOS support, please check for future releases or contribute to the project.

## Quick Start

### Installation

```bash
pip install django-udp-discovery
```

### Basic Usage

1. Add to your Django `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your other apps
    'django_udp_discovery',
]
```

2. The UDP discovery service starts automatically when Django loads!

3. Clients can now discover your server by sending a UDP message to port 9999 (default).

### Manual Control

#### Using Management Command

The `start_discovery` management command provides enhanced control over the UDP discovery service:

```bash
# Start the service (runs indefinitely)
python manage.py start_discovery

# Start the service for a specific duration (in seconds)
python manage.py start_discovery --duration 60   # Run for 60 seconds
python manage.py start_discovery --duration 120   # Run for 120 seconds (2 minutes)
python manage.py start_discovery --duration 3600  # Run for 3600 seconds (1 hour)
```

**Features:**
- Automatically stops any existing service before starting
- Handles port conflicts by freeing the port and restarting
- Optional duration-based auto-stop with automatic cleanup
- Graceful shutdown on Ctrl+C interruption

#### Using Python API

```python
from django_udp_discovery import start_udp_service, stop_udp_service, is_running

# Check if service is running
if is_running():
    print("Discovery service is active")

# Manually start/stop if needed
start_udp_service()
stop_udp_service()
```

## Configuration

Customize the discovery service in your Django `settings.py`:

```python
# UDP Discovery Settings
DISCOVERY_PORT = 9999              # UDP port for discovery (default: 9999)
DISCOVERY_MESSAGE = "DISCOVER_SERVER"  # Discovery message (default: "DISCOVER_SERVER")
RESPONSE_PREFIX = "SERVER_IP:"     # Response prefix (default: "SERVER_IP:")
DISCOVERY_TIMEOUT = 0.5            # Client timeout in seconds (default: 0.5)
DISCOVERY_BUFFER_SIZE = 1024       # UDP buffer size in bytes (default: 1024)
ENABLE_LOGGING = True              # Enable logging (default: True)
```

### Debugging and Console Logging

To enable debugging and see detailed information in the console about the UDP discovery service, you **must** add the following logging configuration to your Django project's `settings.py`:

```python
# Logging configuration
# https://docs.djangoproject.com/en/5.2/topics/logging/
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django_udp_discovery': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
```

This configuration will output debug information to the console, including:
- Service startup and shutdown events
- Discovery request messages received
- Server responses sent
- Error messages and port conflicts
- Service status changes

**Note**: The log level automatically adjusts based on your `DEBUG` setting - `DEBUG` level when `DEBUG=True`, `INFO` level when `DEBUG=False`.

## How It Works

1. **Server Side**: When Django starts, a background thread begins listening on the configured UDP port
2. **Client Discovery**: Clients send a UDP broadcast with the discovery message
3. **Server Response**: The server validates the message and responds with its IP address
4. **Client Connection**: Clients receive the IP and can connect to the server

## Protocol

The discovery protocol is simple:

- **Discovery Message**: Client sends `DISCOVER_SERVER` (configurable) as a UDP message
- **Response Format**: Server responds with `SERVER_IP:<ip_address>` (configurable prefix)
- **Port**: Default 9999 (configurable)

## Requirements

- Python 3.7+
- Django 3.4+ (or Django 2.2+ with app config)

## Testing

Run the test suite:

```bash
python manage.py test django_udp_discovery
```

### Test Results

Latest test results are available in the [test_results](test_results/README.md) directory. All 21 tests pass successfully, covering:

- Configuration management (4 tests)
- UDP listener service lifecycle (6 tests)
- Management command functionality (11 tests)

See [test_results/README.md](test_results/README.md) for detailed test results and coverage information.

## Documentation

Comprehensive documentation is available in the following locations:

- **[Package Documentation](src/django_udp_discovery/README.md)** - Detailed package documentation, module descriptions, and usage examples

## Project Structure

```
django-udp-discovery/
├── src/                         # Source code directory
│   └── django_udp_discovery/    # Python package (installable)
│       ├── __init__.py          # Package initialization
│       ├── apps.py              # Django app configuration
│       ├── conf.py              # Configuration management
│       ├── listener.py          # UDP listener implementation
│       ├── utility.py           # Common utility functions
│       ├── README.md            # Package documentation
│       └── management/          # Django management commands
│           └── commands/
│               └── start_discovery.py  # Manual service control command
├── tests/                       # Test suite (not in package)
│   └── tests.py                 # Comprehensive test suite
├── test_project/                # Test Django project (for prototyping)
├── test_results/                # Test results and reports (gitignored)
│   ├── README.md                # Test results summary
│   └── test_output.txt          # Full test output
├── pyproject.toml               # Package configuration (PEP 621)
├── MANIFEST.in                  # Package manifest
├── LICENSE                      # MIT License
└── README.md                    # This file
```

## Production Usage Examples

### Example 1: Basic Server Setup

A complete example of setting up a Django server with UDP discovery:

**`settings.py`**:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_udp_discovery',  # Add this
]

# UDP Discovery Configuration
DISCOVERY_PORT = 9999
DISCOVERY_MESSAGE = "DISCOVER_SERVER"
RESPONSE_PREFIX = "SERVER_IP:"
ENABLE_LOGGING = True

# Logging configuration for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django_udp_discovery': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
```

The service will start automatically when you run your Django server:
```bash
python manage.py runserver
```

### Example 2: Production Server with Custom Configuration

For production environments, you may want to customize the discovery settings:

**`settings.py`** (production):
```python
# Production UDP Discovery Settings
DISCOVERY_PORT = 7777  # Custom port
DISCOVERY_MESSAGE = "FIND_MY_SERVER"  # Custom discovery message
RESPONSE_PREFIX = "my_server_ip:"  # Custom response prefix
ENABLE_LOGGING = True

# Production logging (INFO level, not DEBUG)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django_udp_discovery': {
            'handlers': ['console'],
            'level': 'INFO',  # Use INFO for production
            'propagate': False,
        },
    },
}
```

### Example 4: Using the Management Command in Production

For production deployments, you can use the management command to control the service:

```bash
# Start for a specific duration (useful for scheduled tasks)
python manage.py start_discovery --duration 3600  # 1 hour

# Use with process managers like systemd or supervisor
# systemd service example:
# [Service]
# ExecStart=/path/to/venv/bin/python /path/to/manage.py start_discovery
```

### Example 5: Programmatic Control

Control the service programmatically in your Django views or management commands:

```python
from django_udp_discovery import start_udp_service, stop_udp_service, is_running
from django.http import JsonResponse

def service_status(request):
    """API endpoint to check discovery service status"""
    return JsonResponse({
        'running': is_running(),
        'status': 'active' if is_running() else 'inactive'
    })

def start_service(request):
    """API endpoint to start the discovery service"""
    if start_udp_service():
        return JsonResponse({'status': 'started'})
    return JsonResponse({'status': 'failed'}, status=500)

def stop_service(request):
    """API endpoint to stop the discovery service"""
    if stop_udp_service():
        return JsonResponse({'status': 'stopped'})
    return JsonResponse({'status': 'failed'}, status=500)
```

## License

See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or contributions, please use the project's issue tracker.
