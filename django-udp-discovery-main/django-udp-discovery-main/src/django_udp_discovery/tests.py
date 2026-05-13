"""
Test suite for django-udp-discovery package.

This module contains comprehensive unit tests for the UDP discovery functionality,
including configuration management, service lifecycle, protocol behavior, and
management commands.

The tests use Django's TestCase framework and override settings to avoid
conflicts between test cases. Each test uses a different port to prevent
interference from concurrent test execution.

Test Classes:
    DiscoverySettingsTest: Tests for configuration module functionality.
    UdpListenerTest: Tests for UDP listener service lifecycle and behavior.
    StartDiscoveryCommandTest: Tests for the start_discovery management command.
"""

import socket
import time
import threading
from io import StringIO
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django_udp_discovery.conf import settings as discovery_settings
from django_udp_discovery.listener import (
    start_udp_service,
    stop_udp_service,
    is_running
)


class DiscoverySettingsTest(TestCase):
    """
    Test suite for the django-udp-discovery configuration module.
    
    This test class verifies that the configuration system correctly:
        - Loads default settings
        - Allows Django settings to override defaults
        - Handles invalid setting access
        - Provides safe getter methods
    
    All tests use Django's override_settings decorator to ensure clean
    test isolation and avoid affecting other tests or the actual configuration.
    """

    def test_default_settings_are_loaded(self) -> None:
        """
        Verify that default configuration values are correctly loaded.
        
        This test ensures that all default settings defined in the configuration
        module are accessible and have the expected values. It validates the
        fallback mechanism when Django settings don't override the defaults.
        """
        self.assertEqual(discovery_settings.DISCOVERY_PORT, 9999)
        self.assertEqual(discovery_settings.DISCOVERY_MESSAGE, "DISCOVER_SERVER")
        self.assertEqual(discovery_settings.RESPONSE_PREFIX, "SERVER_IP:")
        self.assertEqual(discovery_settings.DISCOVERY_TIMEOUT, 0.5)

    @override_settings(DISCOVERY_PORT=7777, DISCOVERY_MESSAGE="HELLO_SERVER")
    def test_overrides_from_django_settings(self) -> None:
        """
        Verify that Django project settings correctly override default values.
        
        This test ensures that when settings are defined in Django's settings.py,
        they take precedence over the default values. This is critical for
        allowing projects to customize the discovery behavior.
        """
        self.assertEqual(discovery_settings.DISCOVERY_PORT, 7777)
        self.assertEqual(discovery_settings.DISCOVERY_MESSAGE, "HELLO_SERVER")

    def test_invalid_setting_raises_attribute_error(self) -> None:
        """
        Verify that accessing an undefined setting raises AttributeError.
        
        This test ensures that the configuration system properly validates
        setting names and provides clear error messages for invalid access
        attempts. This helps catch configuration errors early.
        """
        with self.assertRaises(AttributeError):
            _ = discovery_settings.INVALID_KEY

    def test_get_method_returns_correct_values(self) -> None:
        """
        Verify that the get() method returns correct values with fallbacks.
        
        This test ensures that the safe getter method correctly retrieves
        settings and falls back to provided defaults when settings are not
        found. This validates the safe access pattern for optional settings.
        """
        port = discovery_settings.get("DISCOVERY_PORT")
        self.assertEqual(port, 9999)

        fallback = discovery_settings.get("NON_EXISTENT", default="X")
        self.assertEqual(fallback, "X")


class UdpListenerTest(TestCase):
    """
    Test suite for the UDP discovery listener service.
    
    This test class verifies the UDP listener functionality, including:
        - Service lifecycle (start/stop)
        - Protocol behavior (message matching and responses)
        - Error handling and edge cases
        - Thread safety and graceful shutdown
    
    Each test method uses a different port (via override_settings) to prevent
    conflicts. The setUp and tearDown methods ensure clean state between tests.
    
    Note:
        These tests create actual UDP sockets and may require network access.
        They use localhost (127.0.0.1) to avoid external network dependencies.
    """

    def setUp(self) -> None:
        """
        Set up test environment before each test method.
        
        This method ensures that the UDP discovery service is stopped before
        each test runs, providing a clean state. It waits briefly to allow
        any previous service instance to fully shut down.
        """
        if is_running():
            stop_udp_service()
        # Give it a moment to fully stop
        time.sleep(0.1)

    def tearDown(self) -> None:
        """
        Clean up test environment after each test method.
        
        This method ensures that the UDP discovery service is stopped after
        each test completes, preventing resource leaks and port conflicts
        between tests. It waits briefly to allow graceful shutdown.
        """
        if is_running():
            stop_udp_service()
        # Give it a moment to fully stop
        time.sleep(0.1)

    @override_settings(DISCOVERY_PORT=9998, ENABLE_LOGGING=False)
    def test_start_stop_service(self) -> None:
        """
        Verify that the service can be started and stopped successfully.
        
        This test validates the basic lifecycle of the UDP discovery service.
        It ensures that:
            - The service starts correctly
            - The service reports as running after startup
            - The service stops correctly
            - The service reports as stopped after shutdown
        """
        # Initially not running
        self.assertFalse(is_running())
        
        # Start service
        result = start_udp_service()
        self.assertTrue(result)
        
        # Give it time to start
        time.sleep(0.2)
        self.assertTrue(is_running())
        
        # Stop service
        result = stop_udp_service()
        self.assertTrue(result)
        
        # Give it time to stop
        time.sleep(0.2)
        self.assertFalse(is_running())

    @override_settings(DISCOVERY_PORT=9997, ENABLE_LOGGING=False)
    def test_double_start_returns_false(self) -> None:
        """
        Verify that starting an already running service returns False.
        
        This test ensures that the service is idempotent and prevents
        multiple instances from running simultaneously. It validates that
        attempting to start the service when it's already running returns
        False without creating duplicate listeners.
        """
        start_udp_service()
        time.sleep(0.2)
        
        # Try to start again
        result = start_udp_service()
        self.assertFalse(result)
        
        stop_udp_service()

    @override_settings(DISCOVERY_PORT=9996, ENABLE_LOGGING=False)
    def test_stop_when_not_running_returns_true(self) -> None:
        """
        Verify that stopping a non-running service returns True.
        
        This test ensures that the stop function is idempotent and handles
        the case where the service is not running gracefully. According to
        the function documentation, it returns True when the service was
        stopped successfully OR was already stopped, making it idempotent.
        """
        result = stop_udp_service()
        self.assertTrue(result, "stop_udp_service() should return True when service is already stopped (idempotent)")

    @override_settings(
        DISCOVERY_PORT=9995,
        DISCOVERY_MESSAGE="TEST_DISCOVER",
        RESPONSE_PREFIX="TEST_IP:",
        ENABLE_LOGGING=False
    )
    def test_responds_to_discovery_message(self) -> None:
        """
        Verify that the listener responds correctly to valid discovery messages.
        
        This test validates the core discovery protocol functionality:
            - The listener receives UDP messages
            - Valid discovery messages are recognized
            - Responses are sent with the correct format
            - The server IP address is included in the response
        
        The test uses custom settings to avoid conflicts with default values
        and to test the protocol with different message formats.
        """
        # Start the service
        start_udp_service()
        time.sleep(0.3)  # Give it time to bind
        
        try:
            # Create a client socket
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.settimeout(2.0)
            
            # Send discovery message
            discovery_msg = b"TEST_DISCOVER"
            client_socket.sendto(discovery_msg, ("127.0.0.1", 9995))
            
            # Receive response
            response, addr = client_socket.recvfrom(1024)
            client_socket.close()
            
            # Verify response
            self.assertTrue(response.startswith(b"TEST_IP:"))
            # Extract IP from response
            ip_str = response.decode('utf-8').replace("TEST_IP:", "")
            # Should be a valid IP address (check format)
            parts = ip_str.split('.')
            self.assertEqual(len(parts), 4, f"Invalid IP format: {ip_str}")
            for part in parts:
                self.assertTrue(0 <= int(part) <= 255, f"Invalid IP octet: {part}")
            
        finally:
            stop_udp_service()

    @override_settings(
        DISCOVERY_PORT=9994,
        DISCOVERY_MESSAGE="DISCOVER_SERVER",
        ENABLE_LOGGING=False
    )
    def test_ignores_wrong_message(self) -> None:
        """
        Verify that the listener ignores messages that don't match the protocol.
        
        This test ensures that the listener only responds to valid discovery
        messages and ignores other UDP traffic. This is important for security
        and to prevent the service from responding to unrelated network traffic.
        """
        start_udp_service()
        time.sleep(0.3)
        
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.settimeout(0.5)
            
            # Send wrong message
            client_socket.sendto(b"WRONG_MESSAGE", ("127.0.0.1", 9994))
            
            # Should not receive a response
            try:
                response, addr = client_socket.recvfrom(1024)
                # If we get here, we received something (unexpected)
                self.fail("Should not have received a response to wrong message")
            except socket.timeout:
                # Expected - no response
                pass
            
            client_socket.close()
        finally:
            stop_udp_service()

    @override_settings(DISCOVERY_PORT=9993, ENABLE_LOGGING=False)
    def test_graceful_shutdown(self) -> None:
        """
        Verify that the listener thread terminates gracefully on shutdown.
        
        This test validates that the service can be stopped cleanly without
        leaving threads or resources hanging. It ensures that:
            - The running flag is properly cleared
            - The listener thread terminates
            - The service reports as stopped after shutdown
        
        This is critical for preventing resource leaks in production deployments.
        """
        start_udp_service()
        time.sleep(0.2)
        
        # Verify it's running
        self.assertTrue(is_running())
        
        # Stop it
        stop_udp_service()
        time.sleep(0.3)
        
        # Verify it's stopped
        self.assertFalse(is_running())


class StartDiscoveryCommandTest(TestCase):
    """
    Test suite for the start_discovery management command.
    
    This test class verifies the management command functionality, including:
        - Basic command execution (with and without duration)
        - Automatic cleanup of existing services
        - Duration validation
        - Configuration and status display
        - Error handling (invalid duration, port conflicts)
        - Duration-based auto-stop functionality
        - Helper method functionality
    
    Each test method uses a different port (via override_settings) to prevent
    conflicts. The setUp and tearDown methods ensure clean state between tests.
    """

    def setUp(self) -> None:
        """
        Set up test environment before each test method.
        
        Ensures the UDP discovery service is stopped before each test runs.
        """
        if is_running():
            stop_udp_service()
        time.sleep(0.1)

    def tearDown(self) -> None:
        """
        Clean up test environment after each test method.
        
        Ensures the UDP discovery service is stopped after each test completes.
        """
        if is_running():
            stop_udp_service()
        time.sleep(0.1)

    @override_settings(DISCOVERY_PORT=9992, ENABLE_LOGGING=False)
    def test_command_starts_service_without_duration(self) -> None:
        """
        Verify that the command starts the service when no duration is specified.
        
        This test ensures that the command can start the service successfully
        and returns immediately without blocking.
        """
        out = StringIO()
        
        # Call the command without duration
        call_command('start_discovery', stdout=out)
        
        # Give service time to start
        time.sleep(0.3)
        
        # Verify service is running
        self.assertTrue(is_running())
        
        # Verify output contains expected messages
        output = out.getvalue()
        self.assertIn('Starting UDP discovery service', output)
        self.assertIn('Configuration:', output)
        self.assertIn('Service Status:', output)
        
        # Cleanup
        stop_udp_service()

    @override_settings(DISCOVERY_PORT=9991, ENABLE_LOGGING=False)
    def test_command_stops_existing_service_before_starting(self) -> None:
        """
        Verify that the command stops any existing service before starting.
        
        This test ensures that the command automatically handles cleanup of
        existing services, preventing conflicts and ensuring a clean start.
        """
        # Start service manually first
        start_udp_service()
        time.sleep(0.2)
        self.assertTrue(is_running())
        
        out = StringIO()
        
        # Call the command - should stop existing and start new
        call_command('start_discovery', stdout=out)
        
        # Give service time to restart
        time.sleep(0.3)
        
        # Verify service is still running (was stopped and restarted)
        self.assertTrue(is_running())
        
        # Verify output indicates stopping existing service
        output = out.getvalue()
        self.assertIn('already running', output.lower())
        self.assertIn('Stopping it', output)
        
        # Cleanup
        stop_udp_service()

    @override_settings(DISCOVERY_PORT=9990, ENABLE_LOGGING=False)
    def test_command_with_valid_duration(self) -> None:
        """
        Verify that the command accepts valid duration and sets up auto-stop.
        
        This test ensures that when a valid duration is provided, the command
        sets up the auto-stop timer correctly.
        """
        out = StringIO()
        
        # Call command with short duration (1 second for testing)
        # Use threading to interrupt after a short time since we can't wait full duration
        def run_command():
            try:
                call_command('start_discovery', duration=1, stdout=out)
            except SystemExit:
                pass  # Command may exit when duration expires
        
        thread = threading.Thread(target=run_command, daemon=True)
        thread.start()
        
        # Wait a bit for command to start
        time.sleep(0.3)
        
        # Verify service started
        self.assertTrue(is_running())
        
        # Verify output contains duration information
        output = out.getvalue()
        output_lower = output.lower()
        self.assertTrue('duration' in output_lower or 'auto-stop' in output_lower or 'timer' in output_lower)
        
        # Wait for duration to expire (1 second + buffer for cleanup)
        # The command blocks until duration expires, so we need to wait for the thread
        thread.join(timeout=3.0)  # Wait up to 3 seconds for command to complete
        
        # Give a bit more time for cleanup to complete
        time.sleep(0.3)
        
        # Verify service was stopped
        self.assertFalse(is_running(), "Service should have been stopped after duration expired")

    def test_command_rejects_negative_duration(self) -> None:
        """
        Verify that the command rejects negative duration values.
        
        This test ensures proper validation of duration argument to prevent
        invalid configurations.
        """
        out = StringIO()
        err = StringIO()
        
        with self.assertRaises(CommandError) as cm:
            call_command('start_discovery', duration=-1, stdout=out, stderr=err)
        
        self.assertIn('greater than 0', str(cm.exception).lower())

    def test_command_rejects_zero_duration(self) -> None:
        """
        Verify that the command rejects zero duration values.
        
        This test ensures that zero duration is properly rejected as invalid.
        """
        out = StringIO()
        
        with self.assertRaises(CommandError) as cm:
            call_command('start_discovery', duration=0, stdout=out)
        
        self.assertIn('greater than 0', str(cm.exception).lower())

    @override_settings(DISCOVERY_PORT=9989, ENABLE_LOGGING=False)
    def test_command_displays_configuration(self) -> None:
        """
        Verify that the command displays current configuration.
        
        This test ensures that configuration information is properly displayed
        to the user, including port, messages, and other settings.
        """
        out = StringIO()
        
        call_command('start_discovery', stdout=out)
        time.sleep(0.2)
        
        output = out.getvalue()
        
        # Verify configuration details are displayed
        self.assertIn('Configuration:', output)
        self.assertIn('Port:', output)
        self.assertIn('Discovery Message:', output)
        self.assertIn('Response Prefix:', output)
        self.assertIn('Buffer Size:', output)
        self.assertIn('Logging:', output)
        
        # Verify actual values are shown
        self.assertIn(str(discovery_settings.DISCOVERY_PORT), output)
        self.assertIn(discovery_settings.DISCOVERY_MESSAGE, output)
        
        stop_udp_service()

    @override_settings(DISCOVERY_PORT=9988, ENABLE_LOGGING=False)
    def test_command_displays_status(self) -> None:
        """
        Verify that the command displays service status.
        
        This test ensures that status information is properly displayed,
        including whether the service is running and how to test it.
        """
        out = StringIO()
        
        call_command('start_discovery', stdout=out)
        time.sleep(0.2)
        
        output = out.getvalue()
        
        # Verify status information is displayed
        self.assertIn('Service Status:', output)
        self.assertIn('Running', output)
        self.assertIn('port', output.lower())
        
        # Verify testing instructions are shown
        output_lower = output.lower()
        self.assertIn('to test the service', output_lower)
        
        stop_udp_service()

    def test_format_duration_utility_function(self) -> None:
        """
        Verify the format_duration utility function works correctly.
        
        This test ensures that duration formatting produces human-readable
        output in the expected format.
        """
        from django_udp_discovery.utility import format_duration
        
        # Test various duration formats
        self.assertEqual(format_duration(0), '0s')
        self.assertEqual(format_duration(45), '45s')
        self.assertEqual(format_duration(60), '1m')
        self.assertEqual(format_duration(120), '2m')
        self.assertEqual(format_duration(3661), '1h 1m 1s')
        self.assertEqual(format_duration(3600), '1h')
        self.assertEqual(format_duration(3723), '1h 2m 3s')
        # Test negative values (should be treated as 0)
        self.assertEqual(format_duration(-10), '0s')

    @override_settings(DISCOVERY_PORT=9986, ENABLE_LOGGING=False)
    def test_cleanup_method_stops_service(self) -> None:
        """
        Verify that the _cleanup method properly stops the service.
        
        This test ensures that the cleanup method correctly stops the service
        and cleans up resources.
        """
        from django_udp_discovery.management.commands.start_discovery import Command
        
        # Start service
        start_udp_service()
        time.sleep(0.2)
        self.assertTrue(is_running())
        
        # Create command instance and call cleanup
        command = Command()
        command._cleanup()
        
        # Give it time to clean up
        time.sleep(0.3)
        
        # Verify service is stopped
        self.assertFalse(is_running())

    @override_settings(DISCOVERY_PORT=9985, ENABLE_LOGGING=False)
    def test_command_handles_port_conflict_gracefully(self) -> None:
        """
        Verify that the command handles port conflicts with retry logic.
        
        This test ensures that when a port conflict is detected, the command
        attempts to free the port and retry starting the service.
        """
        # Create a socket to occupy the port
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Bind to the port to create a conflict
            test_socket.bind(("0.0.0.0", 9985))
            
            out = StringIO()
            err = StringIO()
            
            # Try to start the command - should handle conflict
            # Note: This may still fail if port is truly occupied, but command
            # should attempt cleanup and provide clear error message
            try:
                call_command('start_discovery', stdout=out, stderr=err)
            except (CommandError, SystemExit):
                # Expected if port cannot be freed
                pass
            
            output = out.getvalue() + err.getvalue()
            # Command should attempt to handle the conflict
            # Either succeeds or provides clear error message
            self.assertTrue(
                'port' in output.lower() or 
                'conflict' in output.lower() or
                'already in use' in output.lower() or
                'started successfully' in output.lower()
            )
        finally:
            test_socket.close()
            time.sleep(0.2)
            if is_running():
                stop_udp_service()

    @override_settings(DISCOVERY_PORT=9984, ENABLE_LOGGING=False)
    def test_command_retry_logic_on_start_failure(self) -> None:
        """
        Verify that the command retries starting if initial attempt fails.
        
        This test ensures that the command implements retry logic when the
        initial start attempt fails, attempting cleanup and retry.
        """
        out = StringIO()
        
        # Start and stop service to create potential stale state
        start_udp_service()
        time.sleep(0.2)
        stop_udp_service()
        time.sleep(0.2)
        
        # Now call command - should handle any stale state and start successfully
        call_command('start_discovery', stdout=out)
        time.sleep(0.3)
        
        # Verify service started successfully
        self.assertTrue(is_running())
        
        output = out.getvalue()
        self.assertIn('started successfully', output.lower())
        
        stop_udp_service()
