"""
Django management command to manually start the UDP discovery service.

This module provides a Django management command that allows developers and
administrators to start the UDP discovery listener manually for debugging,
testing, or verification purposes. The command includes automatic cleanup
of existing services, port conflict resolution, and optional duration-based
execution with automatic shutdown.

The command extends Django's BaseCommand class and provides:
    - Automatic stopping of existing services before starting
    - Port conflict detection and resolution
    - Duration-based execution with automatic cleanup
    - Graceful shutdown handling (Ctrl+C support)
    - Comprehensive error handling and user feedback

Usage:
    Basic usage (runs indefinitely)::
    
        python manage.py start_discovery
    
    With duration (auto-stops after specified seconds)::
    
        python manage.py start_discovery --duration 60    # 60 seconds
        python manage.py start_discovery --duration 120   # 2 minutes
        python manage.py start_discovery --duration 3600   # 1 hour

Command Behavior:
    When executed, the command will:
    
    1. Check if a UDP discovery service is already running
    2. Stop any existing service and free the port if needed
    3. Display current configuration (port, messages, etc.)
    4. Start the UDP discovery service on the configured port
    5. If duration is specified, set up an auto-stop timer
    6. Wait for duration to expire or user interruption (Ctrl+C)
    7. Automatically clean up resources when stopping

Error Handling:
    The command handles various error scenarios:
    
    - Port conflicts: Attempts to free the port and retry
    - Service already running: Automatically stops and restarts
    - Invalid duration: Validates and provides clear error messages
    - Network errors: Provides detailed error information

Examples:
    Start service for testing (runs for 2 minutes)::
    
        python manage.py start_discovery --duration 120
    
    Start service indefinitely (until manually stopped)::
    
        python manage.py start_discovery
    
    Stop early: Press Ctrl+C to interrupt and clean up

See Also:
    :mod:`django_udp_discovery.listener`: Core UDP listener implementation
    :mod:`django_udp_discovery.conf`: Configuration settings
    :class:`django.core.management.base.BaseCommand`: Django command base class
"""

import time
import threading
from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django_udp_discovery.listener import start_udp_service, stop_udp_service, is_running
from django_udp_discovery.conf import settings
from django_udp_discovery.utility import format_duration, is_port_error


class Command(BaseCommand):
    """
    Django management command to start the UDP discovery service manually.
    
    This command provides manual control over the UDP discovery listener,
    allowing it to be started independently of Django's automatic startup
    mechanism. It is particularly useful for:
    
    - Debugging and testing the discovery service
    - Restarting the service without restarting Django
    - Running the service for a limited duration
    - Verifying service configuration and status
    
    The command automatically handles cleanup of existing services, resolves
    port conflicts, and provides optional duration-based execution with
    automatic shutdown.
    
    Attributes:
        help (str): Short description of the command displayed in help.
        _timer_thread (threading.Thread, optional): Thread used for duration-based
            auto-stop functionality. Set to None when not in use.
        _should_stop (bool): Flag indicating whether the service should stop.
            Used for coordination between the main thread and timer thread.
    
    Example:
        Basic usage::
        
            python manage.py start_discovery
        
        With duration::
        
            python manage.py start_discovery --duration 120
        
    Note:
        The command will block execution when a duration is specified,
        waiting for the timer to expire or user interruption. Without
        duration, the command returns immediately after starting the service.
    
    See Also:
        :meth:`handle`: Main command execution method
        :meth:`add_arguments`: Command argument definitions
    """
    
    help: str = 'Start the UDP discovery service manually'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the command instance.
        
        Sets up internal state variables for timer thread management and
        shutdown coordination. This method is called by Django when the
        command is instantiated.
        
        Args:
            *args: Variable length argument list passed to parent class.
            **kwargs: Arbitrary keyword arguments passed to parent class.
        
        Note:
            The timer thread and stop flag are initialized to their default
            values (None and False respectively) and will be set during
            command execution if duration-based execution is requested.
        """
        super().__init__(*args, **kwargs)
        self._timer_thread: Optional[threading.Thread] = None
        self._should_stop: bool = False

    def add_arguments(self, parser: Any) -> None:
        """
        Add command-line arguments to the argument parser.
        
        This method is called by Django to register command-line arguments
        that can be passed to the command. Currently defines the `--duration`
        argument for time-limited execution.
        
        Args:
            parser: The argument parser instance provided by Django.
                Arguments are added to this parser. Typically an
                :class:`argparse.ArgumentParser` instance.
        
        Arguments:
            --duration (int, optional): Duration in seconds to run the service
                before automatically stopping. Must be a positive integer.
                If not specified, the service runs indefinitely until manually
                stopped or Django is shut down.
        
        Example:
            The duration argument can be used like::
            
                python manage.py start_discovery --duration 120
        
        Note:
            The duration must be greater than 0. Invalid values will raise
            a :class:`CommandError` during command execution.
        """
        parser.add_argument(
            '--duration',
            type=int,
            default=None,
            help=(
                'Duration to run the service before auto-stopping, specified in seconds. '
                'For example: 60 (1 minute), 120 (2 minutes), 3600 (1 hour). '
                'If not specified, service runs indefinitely.'
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the command to start the UDP discovery service.
        
        This is the main entry point for the command. It orchestrates the
        entire process of starting the UDP discovery service, including
        cleanup of existing services, port conflict resolution, and optional
        duration-based execution.
        
        The method performs the following steps:
        
        1. Validates the duration argument (if provided)
        2. Stops any existing UDP discovery service
        3. Attempts to free the port if it's in use
        4. Displays current configuration to the user
        5. Starts the UDP discovery service
        6. Sets up auto-stop timer if duration is specified
        7. Waits for duration to expire or user interruption
        8. Cleans up resources when stopping
        
        Args:
            *args: Variable length argument list (not used by this command).
            **options: Dictionary of command-line options. Expected keys:
                - duration (int, optional): Duration in seconds for time-limited
                  execution. If None, service runs indefinitely.
        
        Raises:
            CommandError: Raised in the following scenarios:
                - Duration is provided but is less than or equal to 0
                - Service fails to start after cleanup attempts
                - Port is in use by another application and cannot be freed
                - Other unexpected errors occur during service startup
        
        Returns:
            None: This method does not return a value. It may block execution
            if a duration is specified, waiting for the timer to expire.
        
        Example:
            The command is typically invoked via Django's management interface::
            
                python manage.py start_discovery --duration 60
        
        Note:
            - If a duration is specified, this method will block until the
              duration expires or the user interrupts with Ctrl+C
            - The method attempts multiple cleanup and retry strategies if
              the initial start fails
            - All output is written to stdout using Django's command output
              methods for proper formatting
        
        See Also:
            :meth:`_display_configuration`: Display service configuration
            :meth:`_display_status`: Display service status
            :meth:`_setup_auto_stop`: Set up duration-based auto-stop
            :meth:`_cleanup`: Clean up resources
        """
        duration_seconds: Optional[int] = options.get('duration')
        
        if duration_seconds is not None:
            if duration_seconds <= 0:
                raise CommandError('Duration must be greater than 0.')
        
        # Stop any existing service first
        if is_running():
            self.stdout.write(
                self.style.WARNING(
                    'UDP discovery service is already running. Stopping it...'
                )
            )
            stop_udp_service()
            # Wait a moment for cleanup
            time.sleep(0.3)
        
        # Try to free the port if it's in use by attempting to stop again
        # This handles cases where the port might be in use by another process
        # or stale state
        try:
            # Attempt to stop again to ensure clean state
            stop_udp_service()
            time.sleep(0.2)
        except Exception:
            pass  # Ignore errors during cleanup attempt

        # Display configuration before starting
        self.stdout.write('Starting UDP discovery service...')
        if duration_seconds:
            self.stdout.write(
                self.style.WARNING(
                    f'Service will run for {format_duration(duration_seconds)} and then auto-stop.'
                )
            )
        self.stdout.write('')
        self._display_configuration()

        # Attempt to start the service
        try:
            success = start_udp_service()
            
            if success:
                # Give the service a moment to fully initialize
                time.sleep(0.2)
                
                # Verify it's running
                if is_running():
                    self.stdout.write('')
                    self.stdout.write(
                        self.style.SUCCESS(
                            '[OK] UDP discovery service started successfully!'
                        )
                    )
                    self._display_status()
                    
                    # Set up auto-stop timer if duration is specified
                    if duration_seconds:
                        self._setup_auto_stop(duration_seconds)
                        # Keep the command running until timer expires or interrupted
                        try:
                            while not self._should_stop and is_running():
                                time.sleep(0.5)
                        except KeyboardInterrupt:
                            self.stdout.write('')
                            self.stdout.write(
                                self.style.WARNING('Interrupted by user. Stopping service...')
                            )
                            self._cleanup()
                            return
                        
                        # Timer expired, cleanup
                        self._cleanup()
                else:
                    self.stdout.write('')
                    self.stdout.write(
                        self.style.WARNING(
                            'Service started but may not be fully initialized yet.'
                        )
                    )
                    self._display_status()
            else:
                # Service failed to start - try one more time after cleanup
                self.stdout.write(
                    self.style.WARNING(
                        'First start attempt failed. Attempting cleanup and retry...'
                    )
                )
                stop_udp_service()
                time.sleep(0.5)
                
                success = start_udp_service()
                if not success:
                    raise CommandError(
                        'Failed to start UDP discovery service after cleanup. '
                        'The port may be in use by another application.'
                    )
                else:
                    time.sleep(0.2)
                    if is_running():
                        self.stdout.write('')
                        self.stdout.write(
                            self.style.SUCCESS(
                                '[OK] UDP discovery service started successfully after retry!'
                            )
                        )
                        self._display_status()
                        
                        if duration_seconds:
                            self._setup_auto_stop(duration_seconds)
                            try:
                                while not self._should_stop and is_running():
                                    time.sleep(0.5)
                            except KeyboardInterrupt:
                                self.stdout.write('')
                                self.stdout.write(
                                    self.style.WARNING('Interrupted by user. Stopping service...')
                                )
                                self._cleanup()
                                return
                            self._cleanup()
                
        except OSError as e:
            # Handle port binding errors using utility function
            error_msg = str(e)
            if is_port_error(e):
                # Try one more cleanup attempt
                self.stdout.write(
                    self.style.WARNING(
                        'Port conflict detected. Attempting to free the port...'
                    )
                )
                stop_udp_service()
                time.sleep(0.5)
                
                # Try starting again
                try:
                    success = start_udp_service()
                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(
                                '[OK] Port freed and service started successfully!'
                            )
                        )
                        if duration_seconds:
                            self._setup_auto_stop(duration_seconds)
                            try:
                                while not self._should_stop and is_running():
                                    time.sleep(0.5)
                            except KeyboardInterrupt:
                                self.stdout.write('')
                                self.stdout.write(
                                    self.style.WARNING('Interrupted by user. Stopping service...')
                                )
                                self._cleanup()
                                return
                            self._cleanup()
                        return
                except Exception:
                    pass
                
                raise CommandError(
                    f'Port {settings.DISCOVERY_PORT} is already in use by another application. '
                    'Please stop the other application or change DISCOVERY_PORT in settings.'
                )
            else:
                raise CommandError(
                    f'Failed to start UDP discovery service: {error_msg}'
                )
        except Exception as e:
            # Handle any other unexpected errors
            self._cleanup()
            raise CommandError(
                f'Unexpected error while starting UDP discovery service: {e}'
            )

    def _display_configuration(self) -> None:
        """
        Display the current UDP discovery configuration to the user.
        
        This method outputs the current configuration settings that will be
        used by the UDP discovery service. The information is formatted for
        readability and includes all relevant configuration values.
        
        Displayed Information:
            - Discovery port number
            - Discovery message string
            - Response prefix string
            - Buffer size in bytes
            - Logging status (enabled/disabled)
        
        Note:
            This is a private method intended for internal use by the command.
            Configuration values are read from the settings module.
        
        See Also:
            :mod:`django_udp_discovery.conf`: Configuration settings module
        """
        self.stdout.write('Configuration:')
        self.stdout.write(f'  Port: {settings.DISCOVERY_PORT}')
        self.stdout.write(f'  Discovery Message: "{settings.DISCOVERY_MESSAGE}"')
        self.stdout.write(f'  Response Prefix: "{settings.RESPONSE_PREFIX}"')
        self.stdout.write(f'  Buffer Size: {settings.DISCOVERY_BUFFER_SIZE} bytes')
        self.stdout.write(f'  Logging: {"Enabled" if settings.ENABLE_LOGGING else "Disabled"}')

    def _display_status(self) -> None:
        """
        Display the current status of the UDP discovery service.
        
        This method outputs the current operational status of the UDP
        discovery service, including whether it is running and instructions
        on how to test or verify the service functionality.
        
        The status display includes:
            - Current service status (running/not running)
            - Port number on which the service is listening
            - Instructions for testing the service
            - Suggestions for verification methods
        
        Note:
            This is a private method intended for internal use by the command.
            The status is determined by checking the service state via the
            :func:`is_running` function.
        
        See Also:
            :func:`django_udp_discovery.listener.is_running`: Check service status
        """
        self.stdout.write('')
        self.stdout.write('Service Status:')
        
        if is_running():
            self.stdout.write(
                self.style.SUCCESS(f'  Status: Running on port {settings.DISCOVERY_PORT}')
            )
            self.stdout.write('')
            self.stdout.write('To test the service, you can:')
            self.stdout.write(
                f'  1. Send UDP message "{settings.DISCOVERY_MESSAGE}" to port {settings.DISCOVERY_PORT}'
            )
            self.stdout.write('  2. Use the test_client.py script from test_project')
            self.stdout.write('  3. Use: python manage.py test_discovery (if available)')
        else:
            self.stdout.write(
                self.style.ERROR('  Status: Not running')
            )

    def _setup_auto_stop(self, duration_seconds: int) -> None:
        """
        Set up a timer thread to automatically stop the service after a duration.
        
        This method creates and starts a daemon thread that will wait for the
        specified duration and then signal the main command to stop the service.
        The timer thread runs independently and will trigger cleanup when the
        duration expires.
        
        The timer mechanism:
        
        1. Creates a daemon thread that sleeps for the specified duration
        2. After the duration expires, sets the `_should_stop` flag
        3. Displays a message to the user indicating the duration has expired
        4. The main command loop checks this flag and triggers cleanup
        
        Args:
            duration_seconds (int): Number of seconds to run the service before
                automatically stopping. Must be positive.
        
        Note:
            This is a private method intended for internal use by the command.
            The timer thread is created as a daemon thread, meaning it will
            not prevent the program from exiting. The thread reference is
            stored in `_timer_thread` for later cleanup.
        
        See Also:
            :meth:`_cleanup`: Method called when timer expires
            :attr:`_should_stop`: Flag used for timer coordination
            :attr:`_timer_thread`: Thread reference for cleanup
        """
        self._should_stop = False
        
        def timer_callback() -> None:
            """
            Callback function that runs in the timer thread.
            
            This function is executed in a separate thread and waits for the
            specified duration before signaling the main command to stop.
            
            Note:
                This is a nested function that captures the `duration_seconds`
                variable from the enclosing scope.
            """
            time.sleep(duration_seconds)
            if not self._should_stop:
                self._should_stop = True
                self.stdout.write('')
                self.stdout.write(
                    self.style.WARNING(
                        f'Duration expired ({format_duration(duration_seconds)}). Stopping service...'
                    )
                )
        
        self._timer_thread = threading.Thread(target=timer_callback, daemon=True)
        self._timer_thread.start()
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'[TIMER] Auto-stop timer set for {format_duration(duration_seconds)}'
            )
        )
        self.stdout.write('Press Ctrl+C to stop early.')

    def _cleanup(self) -> None:
        """
        Clean up the UDP discovery service and associated resources.
        
        This method performs a comprehensive cleanup of all resources used
        by the command, including:
        
        1. Stopping the UDP discovery service if it's running
        2. Waiting for the timer thread to complete (if active)
        3. Verifying that cleanup was successful
        4. Providing user feedback on cleanup status
        
        The method attempts multiple cleanup strategies if the initial attempt
        fails, including a force stop if the service doesn't stop gracefully.
        
        Cleanup Process:
        
        1. Sets the `_should_stop` flag to prevent timer from triggering
        2. Stops the UDP discovery service via :func:`stop_udp_service`
        3. Waits for timer thread to finish (with 1 second timeout)
        4. Verifies service has stopped
        5. Attempts force stop if service is still running
        6. Displays success or warning message to user
        
        Note:
            This is a private method intended for internal use by the command.
            It is called when:
            - The duration timer expires
            - The user interrupts with Ctrl+C
            - An error occurs during command execution
        
        Warning:
            If the service cannot be stopped after multiple attempts, a
            warning message is displayed, but the method does not raise
            an exception. This allows the command to complete gracefully
            even if cleanup is not fully successful.
        
        See Also:
            :func:`django_udp_discovery.listener.stop_udp_service`: Stop service
            :func:`django_udp_discovery.listener.is_running`: Check service status
        """
        self._should_stop = True
        
        # Stop the service
        if is_running():
            stop_udp_service()
            time.sleep(0.2)
        
        # Wait for timer thread to finish (if running)
        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=1.0)
        
        # Verify cleanup
        if is_running():
            self.stdout.write(
                self.style.WARNING('Service may still be running. Attempting force stop...')
            )
            stop_udp_service()
            time.sleep(0.3)
        
        if is_running():
            self.stdout.write(
                self.style.ERROR('Warning: Service may not have stopped completely.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('[OK] Service stopped and cleaned up successfully.')
            )

