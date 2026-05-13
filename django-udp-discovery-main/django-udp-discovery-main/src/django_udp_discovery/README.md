# django_udp_discovery Package



## Overview

The `django_udp_discovery` package provides a complete UDP discovery solution for Django applications. It enables Django servers to automatically respond to discovery requests from client nodes on a local network, allowing clients to find and connect to the server without hardcoded IP addresses.

## Platform Support

⚠️ **Important**: The current version of `django_udp_discovery` is **not supported on macOS**. This package is designed for Windows and Linux environments. If you need macOS support, please check for future releases or contribute to the project.

## Package Structure

```
django_udp_discovery/
├── __init__.py      # Package initialization and public API exports
├── apps.py          # Django app configuration with auto-startup
├── conf.py          # Configuration management with Django settings integration
├── listener.py      # UDP listener service implementation
├── utility.py       # Common utility functions used across modules
├── README.md        # Package documentation
└── management/      # Django management commands
    └── commands/
        └── start_discovery.py  # Management command for manual service control

Note: tests.py is excluded from the installable package distribution.
```

## Modules

### `__init__.py`
Package initialization module that exports the main public API:
- `start_udp_service()` - Start the UDP discovery service
- `stop_udp_service()` - Stop the UDP discovery service
- `is_running()` - Check if the service is currently running

### `apps.py`
Django application configuration that automatically starts the UDP discovery service when Django loads. The `UdpDiscoveryConfig` class:
- Automatically detects test environments and skips startup
- Integrates with Django's app loading system
- Provides seamless service initialization

### `conf.py`
Configuration management module that provides a unified interface for UDP discovery settings:
- Loads settings from Django's settings.py with fallback to defaults
- Provides safe getter methods for optional settings
- Validates setting names and provides clear error messages

**Available Settings:**
- `DISCOVERY_PORT` - UDP port for discovery service (default: 9999)
- `DISCOVERY_MESSAGE` - Message clients send to discover servers (default: "DISCOVER_SERVER")
- `RESPONSE_PREFIX` - Prefix for server responses (default: "SERVER_IP:")
- `DISCOVERY_TIMEOUT` - Client timeout in seconds (default: 0.5)
- `DISCOVERY_BUFFER_SIZE` - UDP buffer size in bytes (default: 1024)
- `ENABLE_LOGGING` - Enable/disable logging (default: True)

### `listener.py`
Core UDP listener implementation that provides:
- Threaded UDP socket listener running in background
- Automatic server IP detection (uses `utility.get_server_ip()`)
- Protocol message validation and response handling
- Thread-safe service lifecycle management
- Graceful shutdown capabilities
- Comprehensive error handling

**Key Functions:**
- `start_udp_service()` - Start the listener in a daemon thread
- `stop_udp_service()` - Gracefully stop the listener
- `is_running()` - Check service status

### `utility.py`
Common utility functions used across multiple modules in the package:
- **`get_server_ip()`** - Detect the server's local IP address
- **`format_duration()`** - Format seconds into human-readable duration strings
- **`is_port_in_use()`** - Check if a network port is currently in use
- **`validate_port()`** - Validate that a port number is in valid range (1-65535)
- **`is_port_error()`** - Check if an exception indicates a port conflict

These utilities help reduce code duplication and provide consistent functionality
across the package. They are used by:
- `listener.py` - For IP detection and port error handling
- `management/commands/start_discovery.py` - For duration formatting and port error detection
- Test modules - For validation and testing utilities

**Example Usage:**
```python
from django_udp_discovery.utility import get_server_ip, format_duration, is_port_in_use

# Get server IP address
ip = get_server_ip()
print(f"Server IP: {ip}")

# Format duration
duration_str = format_duration(3661)  # "1h 1m 1s"

# Check port availability
if is_port_in_use(9999):
    print("Port 9999 is already in use")
```

### `management/commands/start_discovery.py`
Django management command for manual control of the UDP discovery service:
- Starts the UDP discovery service manually
- Automatically stops existing service before starting
- Handles port conflicts by freeing ports and restarting (uses `utility.is_port_error()`)
- Supports duration-based execution with `--duration` argument (in seconds)
- Automatic cleanup when duration expires
- Graceful shutdown on interruption (Ctrl+C)
- Uses `utility.format_duration()` for human-readable duration display

**Usage:**
```bash
python manage.py runserver                          # Start automatically
python manage.py start_discovery --duration 60      # Run for 60 seconds
python manage.py start_discovery --duration 120     # Run for 120 seconds
```

### `tests.py`
Comprehensive test suite covering:
- Configuration system functionality
- Service lifecycle (start/stop)
- Protocol behavior (message matching and responses)
- Error handling and edge cases
- Thread safety and graceful shutdown

## Usage

### Automatic Startup (Recommended)
The service starts automatically when Django loads. Simply add `django_udp_discovery` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... other apps
    'django_udp_discovery',
]
```

### Manual Control

#### Using Management Command

The `start_discovery` management command provides enhanced control with automatic cleanup and duration-based execution:

```bash
# Start the service for a specific duration (in seconds)
python manage.py start_discovery --duration 60   # Run for 60 seconds
python manage.py start_discovery --duration 120   # Run for 120 seconds (2 minutes)
python manage.py start_discovery --duration 3600  # Run for 3600 seconds (1 hour)
```

**Key Features:**
- **Automatic Cleanup**: Stops any existing service before starting
- **Port Conflict Resolution**: Automatically frees ports if they're in use
- **Duration-Based Execution**: Optionally run for a specified time and auto-stop
- **Graceful Shutdown**: Handles Ctrl+C interruption and cleans up resources

#### Using Python API

If you need programmatic control over the service:

```python
from django_udp_discovery import start_udp_service, stop_udp_service, is_running

# Start the service
if start_udp_service():
    print("Service started")

# Check status
if is_running():
    print("Service is running")

# Stop the service
if stop_udp_service():
    print("Service stopped")
```

### Configuration
Override default settings in your Django `settings.py`:

```python
# Customize discovery settings
DISCOVERY_PORT = 7777
DISCOVERY_MESSAGE = "FIND_SERVER"
RESPONSE_PREFIX = "IP:"
ENABLE_LOGGING = True
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

1. **Service Startup**: When Django loads, the app configuration automatically starts a daemon thread running the UDP listener.

2. **Listening**: The listener binds to the configured UDP port and waits for incoming messages.

3. **Discovery Request**: When a client sends the configured discovery message, the listener validates it.

4. **Response**: If the message matches, the listener responds with the server's IP address using the configured response format.

5. **Shutdown**: The service can be stopped gracefully, closing the socket and terminating the listener thread.

## Thread Safety

All public functions are thread-safe and use locks to prevent race conditions. The service can be started and stopped from any thread safely.

## Error Handling

The package includes comprehensive error handling:
- Port conflicts are detected and logged with clear messages
- Socket errors are caught and logged without crashing
- Invalid settings raise clear AttributeError exceptions
- Service state is validated before operations

## Testing

The test suite is located in the root-level `tests/` directory (not included in the
installable package). To run the tests:

```bash
# From the project root
python test_project/manage.py test django_udp_discovery

# Or if installed
python manage.py test django_udp_discovery
```

The tests use isolated ports to prevent conflicts and include cleanup between test methods.

### Test Results

Latest test results and coverage information are available in the [test_results](../../../../test_results/README.md) directory. All 21 tests pass successfully, covering:
- Configuration management (4 tests)
- UDP listener service lifecycle (6 tests)
- Management command functionality (11 tests)

## Production Usage Examples

### Complete Server Setup Example

```python
# settings.py
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

# Logging configuration for debugging (REQUIRED for console output)
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

## Requirements

- Python 3.7+
- Django 3.2+ (or Django 2.2+ with app config)
- **Windows or Linux** (macOS not currently supported)

## See Also

- [Package Root README](../README.md) - Package distribution information
- [Source Directory README](../../README.md) - Source code organization
- [Project Root README](../../../../README.md) - Project overview and installation

