"""
Utility functions for django-udp-discovery package.

This module provides common utility functions used across multiple modules
in the django-udp-discovery package. These functions are designed to be
reusable and independent of specific module implementations.

Functions:
    get_server_ip(): Detect the server's local IP address.
    format_duration(): Format seconds into human-readable duration strings.
    is_port_in_use(): Check if a port is currently in use.
    validate_port(): Validate that a port number is in the valid range.

These utilities help reduce code duplication and provide consistent
functionality across the package.
"""

import socket
from typing import Optional


def get_server_ip() -> str:
    """
    Determine the server's local IP address.
    
    This function attempts to detect the server's actual network IP address
    by creating a temporary UDP socket and connecting to a public DNS server.
    This method works across different network configurations and avoids
    returning localhost when the server has a real network interface.
    
    The function uses a connection attempt to 8.8.8.8 (Google's public DNS)
    which doesn't actually send data (UDP), but allows the socket to determine
    which network interface would be used for external communication.
    
    This is a utility function that can be used by:
        - The UDP listener to determine the server IP for responses
        - Management commands to display server information
        - Test clients to verify IP detection
        - Any other module that needs to know the server's IP address
    
    Returns:
        str: The server's IP address as a dotted-quad string (e.g., "192.168.1.100").
            Falls back to "127.0.0.1" if IP detection fails.
    
    Example:
        >>> from django_udp_discovery.utility import get_server_ip
        >>> ip = get_server_ip()
        >>> ip
        '192.168.1.100'
        >>> # IP is always a valid format
        >>> parts = ip.split('.')
        >>> len(parts)
        4
    
    Note:
        This function may return "127.0.0.1" if:
        - The server has no network interface
        - Network access is restricted
        - The detection method fails for any reason
        
        The function is safe to call from any thread and does not require
        network access to complete (it will return localhost if detection fails).
    
    See Also:
        :func:`socket.getsockname`: Used internally to get the socket's local address
    """
    try:
        # Create a temporary socket to determine the local IP
        # Connect to a remote address (doesn't actually send data for UDP)
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to a public DNS server (doesn't actually connect for UDP)
            # This allows the socket to determine which network interface would be used
            temp_socket.connect(("8.8.8.8", 80))
            ip = temp_socket.getsockname()[0]
        finally:
            temp_socket.close()
        return ip
    except Exception:
        # Fallback to localhost if detection fails
        return "127.0.0.1"


def format_duration(seconds: int) -> str:
    """
    Format a duration in seconds to a human-readable string representation.
    
    Converts a duration specified in seconds into a more readable format
    that includes hours, minutes, and seconds as appropriate. Only non-zero
    components are included in the output.
    
    This utility function is useful for:
        - Management commands displaying duration information
        - Logging time-based operations
        - User-facing duration displays
        - Any module that needs to present time durations in a readable format
    
    Args:
        seconds (int): Duration in seconds to format. Must be non-negative.
            Negative values will be treated as 0.
    
    Returns:
        str: Human-readable duration string. Examples:
            - "1h 30m 15s" for 5415 seconds
            - "5m" for 300 seconds
            - "60s" for 60 seconds
            - "0s" for 0 seconds
    
    Example:
        >>> from django_udp_discovery.utility import format_duration
        >>> format_duration(3661)
        '1h 1m 1s'
        >>> format_duration(120)
        '2m'
        >>> format_duration(45)
        '45s'
        >>> format_duration(0)
        '0s'
    
    Note:
        The function handles edge cases:
        - Zero seconds returns "0s"
        - Only non-zero components are included
        - At least one component is always displayed (even if 0s)
    
    See Also:
        :func:`time.sleep`: Often used with formatted durations for user feedback
    """
    if seconds < 0:
        seconds = 0
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f'{hours}h')
    if minutes > 0:
        parts.append(f'{minutes}m')
    if secs > 0 or not parts:
        parts.append(f'{secs}s')
    
    return ' '.join(parts)


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a network port is currently in use.
    
    This function attempts to bind to the specified port to determine if
    it's already in use by another process. This is useful for:
        - Validating port availability before starting services
        - Port conflict detection and reporting
        - Testing and debugging port-related issues
    
    Args:
        port (int): The port number to check. Must be in valid range (1-65535).
        host (str, optional): The host address to check. Defaults to "0.0.0.0"
            (all interfaces). Use "127.0.0.1" to check only localhost.
    
    Returns:
        bool: True if the port is in use (cannot bind), False if available.
    
    Example:
        >>> from django_udp_discovery.utility import is_port_in_use
        >>> is_port_in_use(9999)
        False  # Port is available
        >>> # Start a service on port 9999...
        >>> is_port_in_use(9999)
        True  # Port is now in use
    
    Note:
        This function creates a temporary socket to test port availability.
        The socket is immediately closed after the check, so it doesn't
        interfere with actual service binding.
        
        On some systems, this check may have race conditions - a port
        might become available or in use between the check and actual use.
    
    Raises:
        ValueError: If port is not in valid range (1-65535).
        OSError: If there's a system-level error checking the port.
    
    See Also:
        :func:`validate_port`: Validate port number range
        :func:`socket.bind`: Used internally to test port availability
    """
    if not (1 <= port <= 65535):
        raise ValueError(f"Port must be in range 1-65535, got {port}")
    
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            test_socket.bind((host, port))
            return False  # Port is available
        except OSError:
            return True  # Port is in use
        finally:
            test_socket.close()
    except Exception:
        # If we can't check, assume port might be in use to be safe
        return True


def validate_port(port: int) -> bool:
    """
    Validate that a port number is in the valid range.
    
    This utility function checks if a port number is within the valid
    TCP/UDP port range (1-65535). This is useful for:
        - Configuration validation
        - Input validation in management commands
        - Settings validation
        - API parameter validation
    
    Args:
        port (int): The port number to validate.
    
    Returns:
        bool: True if port is valid (1-65535), False otherwise.
    
    Example:
        >>> from django_udp_discovery.utility import validate_port
        >>> validate_port(9999)
        True
        >>> validate_port(0)
        False
        >>> validate_port(65536)
        False
        >>> validate_port(-1)
        False
    
    Note:
        Port 0 is technically valid in some contexts (system-assigned port),
        but this function returns False for it as it's not useful for
        explicit port configuration.
    
    See Also:
        :func:`is_port_in_use`: Check if a valid port is available
    """
    return isinstance(port, int) and (1 <= port <= 65535)


def is_port_error(err: Exception) -> bool:
    """
    Check if an exception indicates a port conflict or binding error.
    
    This utility function helps identify port-related errors across different
    operating systems. It checks for common error codes and messages that
    indicate a port is already in use.
    
    This is useful for:
        - Error handling in listener startup
        - Port conflict detection
        - Providing user-friendly error messages
        - Cross-platform error detection
    
    Args:
        err (Exception): The exception to check. Typically an OSError or
            socket-related exception.
    
    Returns:
        bool: True if the error indicates a port conflict, False otherwise.
    
    Example:
        >>> from django_udp_discovery.utility import is_port_error
        >>> try:
        ...     socket.bind(("0.0.0.0", 9999))
        ... except OSError as e:
        ...     if is_port_error(e):
        ...         print("Port conflict detected")
    
    Note:
        This function checks for:
        - Error codes: 98 (Linux), 10048 (Windows)
        - Error messages containing "Address already in use"
        - Error messages containing "address is already in use"
        
        Different operating systems use different error codes for the same
        condition, so this function provides a unified way to detect them.
    
    See Also:
        :func:`is_port_in_use`: Proactively check port availability
    """
    if isinstance(err, OSError):
        # Check error codes (98 on Linux, 10048 on Windows)
        if hasattr(err, 'errno') and err.errno in (98, 10048):
            return True
        
        # Check error message
        error_msg = str(err).lower()
        if "address already in use" in error_msg or "address is already in use" in error_msg:
            return True
    
    return False

