"""
UDP Discovery Listener Module

This module provides a threaded UDP listener that runs in the background,
listening on a configurable port and responding to discovery messages from
client nodes. The listener operates in a daemon thread, allowing it to run
concurrently with Django without blocking the main application.

The listener implements a simple discovery protocol:
    1. Listens for UDP messages on the configured port
    2. Validates incoming messages against the configured discovery message
    3. Responds with the server's IP address when a valid discovery request is received
    4. Ignores messages that don't match the discovery protocol

The service is thread-safe and provides graceful shutdown capabilities. It
automatically detects the server's IP address (using `utility.get_server_ip()`)
and includes error handling for common network issues like port conflicts
(using `utility.is_port_error()`).

Usage:
    Manual control of the service:
        >>> from django_udp_discovery.listener import start_udp_service, stop_udp_service, is_running
        >>> start_udp_service()
        True
        >>> is_running()
        True
        >>> stop_udp_service()
        True
    
    The service typically starts automatically when Django loads (via apps.py),
    but can be controlled manually if needed.

Thread Safety:
    All public functions are thread-safe and use locks to prevent race conditions
    when starting or stopping the service concurrently.

Error Handling:
    - Port conflicts are detected and logged with clear error messages
    - Socket errors are caught and logged without crashing the application
    - The service gracefully handles shutdown signals and cleanup
"""

import socket
import threading
import logging
from typing import Optional, Tuple

from django_udp_discovery.conf import settings
from django_udp_discovery.utility import get_server_ip

logger = logging.getLogger(__name__)

# Global state
_udp_socket: Optional[socket.socket] = None
_listener_thread: Optional[threading.Thread] = None
_running: bool = False
_lock: threading.Lock = threading.Lock()


def _udp_listener_worker() -> None:
    """
    Worker function that runs in a daemon thread to listen for UDP discovery messages.
    
    This function implements the main UDP listener loop. It:
        1. Creates and binds a UDP socket to the configured port
        2. Enters a loop listening for incoming UDP messages
        3. Validates messages against the configured discovery message
        4. Responds with the server IP address for valid discovery requests
        5. Handles errors gracefully and cleans up on shutdown
    
    The function runs until the global `_running` flag is set to False, at
    which point it performs cleanup and exits. The socket uses a timeout to
    periodically check the `_running` flag, enabling responsive shutdown.
    
    Error Handling:
        - Port binding errors (e.g., "Address already in use") are logged and re-raised
        - Socket timeouts are expected and used for shutdown checking
        - Network errors are logged but don't crash the thread
        - All errors are logged with appropriate detail levels
    
    Thread Safety:
        This function accesses global state (_udp_socket, _running) and should
        only be called from the dedicated listener thread. External synchronization
        is handled by the public API functions.
    
    Note:
        This is an internal function and should not be called directly. Use
        start_udp_service() to start the listener thread.
    
    Raises:
        OSError: If the socket cannot be bound to the configured port (e.g., port
            already in use or insufficient permissions).
    """
    global _udp_socket, _running
    
    try:
        # Create UDP socket
        _udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to the configured port
        port: int = settings.DISCOVERY_PORT
        try:
            _udp_socket.bind(("0.0.0.0", port))
        except OSError as e:
            # Handle "Address already in use" error using utility function
            from django_udp_discovery.utility import is_port_error
            if is_port_error(e):
                logger.error(
                    f"UDP Discovery: Port {port} is already in use. "
                    "Please check if another instance is running or change DISCOVERY_PORT."
                )
                raise
            raise
        
        # Set socket to non-blocking mode for graceful shutdown
        _udp_socket.settimeout(1.0)  # 1 second timeout for checking _running flag
        
        if settings.ENABLE_LOGGING:
            logger.info(f"UDP Discovery listener started on port {port}")
        
        server_ip: str = get_server_ip()
        discovery_message: bytes = settings.DISCOVERY_MESSAGE.encode('utf-8')
        response_prefix: bytes = settings.RESPONSE_PREFIX.encode('utf-8')
        buffer_size: int = settings.DISCOVERY_BUFFER_SIZE
        
        while _running:
            try:
                # Receive data from client
                data, client_address = _udp_socket.recvfrom(buffer_size)
                
                # Check if the message matches the discovery message
                if data == discovery_message:
                    # Prepare response with server IP
                    response: bytes = response_prefix + server_ip.encode('utf-8')
                    
                    # Send response back to the client
                    _udp_socket.sendto(response, client_address)
                    
                    if settings.ENABLE_LOGGING:
                        logger.debug(
                            f"UDP Discovery: Responded to {client_address[0]}:{client_address[1]} "
                            f"with server IP: {server_ip}"
                        )
                elif settings.ENABLE_LOGGING:
                    logger.debug(
                        f"UDP Discovery: Received unexpected message from {client_address}: {data}"
                    )
                    
            except socket.timeout:
                # Timeout is expected - allows us to check _running flag periodically
                continue
            except OSError as e:
                if _running:
                    # Only log if we're still supposed to be running
                    logger.error(f"UDP Discovery: Socket error: {e}")
                break
            except Exception as e:
                if _running:
                    logger.error(f"UDP Discovery: Unexpected error: {e}", exc_info=True)
                break
                
    except Exception as e:
        logger.error(f"UDP Discovery: Failed to start listener: {e}", exc_info=True)
    finally:
        # Clean up socket
        if _udp_socket:
            try:
                _udp_socket.close()
            except Exception:
                pass
            _udp_socket = None
        
        # Reset running flag and thread reference when thread terminates
        # This ensures is_running() returns False after shutdown
        _running = False
        
        if settings.ENABLE_LOGGING:
            logger.info("UDP Discovery listener stopped")


def start_udp_service() -> bool:
    """
    Start the UDP discovery service in a background daemon thread.
    
    This function initializes and starts the UDP discovery listener in a
    separate daemon thread. The thread runs in the background and won't
    prevent the main application from shutting down.
    
    The function is idempotent - calling it multiple times when the service
    is already running will return False without starting additional threads.
    
    Before starting, it checks for stale state (dead threads, unclosed sockets)
    and cleans them up to ensure a fresh start.
    
    The service binds to the port specified in DISCOVERY_PORT setting and
    begins listening for discovery messages. If the port is already in use,
    the function will return False and log an error.
    
    Returns:
        bool: True if the service started successfully, False if:
            - The service is already running
            - The port is already in use
            - The listener thread failed to start
    
    Raises:
        OSError: If socket binding fails (e.g., port already in use, insufficient
            permissions). The error is logged before being raised.
    
    Example:
        >>> from django_udp_discovery.listener import start_udp_service
        >>> if start_udp_service():
        ...     print("Discovery service started")
        ... else:
        ...     print("Service already running or failed to start")
        Discovery service started
    
    Note:
        The service typically starts automatically when Django loads. Manual
        calls to this function are only needed if you've stopped the service
        or need to restart it.
    """
    global _listener_thread, _running, _udp_socket
    
    with _lock:
        # Check if service is actually running (thread alive and flag set)
        if _running and _listener_thread is not None and _listener_thread.is_alive():
            if settings.ENABLE_LOGGING:
                logger.warning("UDP Discovery service is already running")
            return False
        
        # Clean up any stale state (dead thread, unclosed socket)
        if _listener_thread is not None and not _listener_thread.is_alive():
            # Thread is dead, clean up
            _running = False
            _listener_thread = None
        
        if _udp_socket is not None:
            # Socket exists but thread is dead, close it
            try:
                _udp_socket.close()
            except Exception:
                pass
            _udp_socket = None
        
        # Now start fresh
        _running = True
        _listener_thread = threading.Thread(
            target=_udp_listener_worker,
            daemon=True,
            name="UDPDiscoveryListener"
        )
        _listener_thread.start()
        
        # Give the thread a moment to start and bind the socket
        # Use a longer timeout to ensure the thread has time to bind
        _listener_thread.join(timeout=0.3)
        
        # Check if thread is still alive (if it died immediately, there was an error)
        if not _listener_thread.is_alive():
            _running = False
            _listener_thread = None
            # Check if there was a binding error by examining the socket
            if _udp_socket is None:
                # Socket was never created or was closed, thread likely failed
                return False
        
        # Thread is alive, service started successfully
        return True


def stop_udp_service() -> bool:
    """
    Stop the UDP discovery service gracefully.
    
    This function performs a graceful shutdown of the UDP discovery service.
    It sets the running flag to False, closes the UDP socket (which interrupts
    any blocking receive operations), and waits for the listener thread to
    terminate.
    
    The shutdown process includes:
        1. Setting the _running flag to False
        2. Closing the UDP socket to interrupt blocking operations
        3. Waiting for the listener thread to finish (with timeout)
        4. Cleaning up thread and socket references
    
    The function is idempotent - calling it when the service is not running
    or when the thread is already dead will clean up any stale state and return True.
    
    Returns:
        bool: True if the service was stopped successfully or was already stopped,
            False if the listener thread did not terminate within the timeout period
    
    Example:
        >>> from django_udp_discovery.listener import stop_udp_service, is_running
        >>> if is_running():
        ...     stop_udp_service()
        ...     print("Service stopped")
        Service stopped
    
    Note:
        The shutdown timeout is 2 seconds. If the thread doesn't terminate
        within this time, the function returns False but the thread may
        continue running until it naturally exits.
    """
    global _udp_socket, _listener_thread, _running
    
    with _lock:
        # If already stopped, just ensure cleanup
        if not _running and (_listener_thread is None or not _listener_thread.is_alive()):
            # Clean up any stale socket references
            if _udp_socket is not None:
                try:
                    _udp_socket.close()
                except Exception:
                    pass
                _udp_socket = None
            if _listener_thread is not None:
                _listener_thread = None
            return True
        
        # Set running flag to False to signal thread to stop
        _running = False
        
        # Close the socket to interrupt any blocking recvfrom() call
        if _udp_socket:
            try:
                _udp_socket.close()
            except Exception:
                pass
            _udp_socket = None
        
        # Wait for thread to finish (with timeout)
        if _listener_thread and _listener_thread.is_alive():
            _listener_thread.join(timeout=2.0)
            if _listener_thread.is_alive():
                if settings.ENABLE_LOGGING:
                    logger.warning("UDP Discovery listener thread did not terminate within timeout")
                return False
        
        # Clean up references
        _listener_thread = None
        
        if settings.ENABLE_LOGGING:
            logger.info("UDP Discovery service stopped")
        
        return True



def is_running() -> bool:
    """
    Check if the UDP discovery service is currently running.
    
    This function checks the current state of the UDP discovery service by
    verifying both the running flag and the listener thread's status. This
    provides a reliable way to determine if the service is active.
    
    If the thread is dead but the flag is still True (e.g., after Django shutdown),
    this function will reset the state and return False. This ensures that
    after Django is stopped with Ctrl+C, is_running() will correctly return False.
    
    Returns:
        bool: True if the service is running (flag is set and thread is alive),
            False otherwise.
    
    Example:
        >>> from django_udp_discovery.listener import is_running, start_udp_service
        >>> is_running()
        False
        >>> start_udp_service()
        True
        >>> is_running()
        True
    
    Note:
        This function provides a snapshot of the service state. The state may
        change immediately after this function returns, so it should not be
        used for synchronization purposes.
    """
    global _running, _listener_thread
    
    with _lock:
        # If thread exists but is dead, clean up the state
        # This handles the case where Django was stopped with Ctrl+C
        if _listener_thread is not None and not _listener_thread.is_alive():
            # Thread died (e.g., Django shutdown), reset state
            _running = False
            _listener_thread = None
    
    return _running and _listener_thread is not None and _listener_thread.is_alive()

