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
    DiscoveryCryptoHardeningTest: Token TTL, tamper detection, replay cache, request parsing.
    EncryptedListenerHardeningTest: Listener nonce echo, replay, expiry and tamper handling.
    KeyRotationTest: Previous-key acceptance and keyring configuration.
    StartDiscoveryCommandTest: Tests for the start_discovery management command.
"""

import base64
import os
import socket
import sys
import time
import threading
from io import StringIO
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from django.test import TestCase, SimpleTestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django_udp_discovery.conf import settings as discovery_settings
from django_udp_discovery import crypto as discovery_crypto
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
        self.assertEqual(discovery_settings.DISCOVERY_SECRET_KEY, "")
        self.assertFalse(discovery_settings.DISCOVERY_ENCRYPTION_ENABLED)

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


class DiscoveryCryptoUtilityTest(SimpleTestCase):
    """Tests for Fernet key resolution, validation, and safe decrypt (no UDP)."""

    def test_validate_fernet_key_accepts_generated_key(self) -> None:
        key = Fernet.generate_key()
        out = discovery_crypto.validate_fernet_key(key)
        self.assertEqual(out, key)
        out_str = discovery_crypto.validate_fernet_key(key.decode("ascii"))
        self.assertEqual(out_str, key)

    def test_validate_fernet_key_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            discovery_crypto.validate_fernet_key("")
        with self.assertRaises(ValueError):
            discovery_crypto.validate_fernet_key(b"")

    def test_validate_fernet_key_rejects_garbage(self) -> None:
        with self.assertRaises(ValueError):
            discovery_crypto.validate_fernet_key("not-a-fernet-key")

    def test_validate_fernet_key_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            discovery_crypto.validate_fernet_key(123)  # type: ignore[arg-type]

    def test_encrypt_decrypt_roundtrip(self) -> None:
        f = Fernet(Fernet.generate_key())
        token = discovery_crypto.encrypt_bytes(b"hello", f)
        plain = discovery_crypto.decrypt_bytes(token, f)
        self.assertEqual(plain, b"hello")

    def test_decrypt_bytes_invalid_token_returns_none(self) -> None:
        a = Fernet(Fernet.generate_key())
        b = Fernet(Fernet.generate_key())
        token = discovery_crypto.encrypt_bytes(b"secret", a)
        self.assertIsNone(discovery_crypto.decrypt_bytes(token, b))

    def test_decrypt_bytes_garbage_returns_none(self) -> None:
        f = Fernet(Fernet.generate_key())
        self.assertIsNone(discovery_crypto.decrypt_bytes(b"not-a-token", f))

    @override_settings(DISCOVERY_SECRET_KEY="")
    def test_resolve_empty_django_explicit_skips_env(self) -> None:
        env_key = Fernet.generate_key().decode("ascii")
        with patch.dict(os.environ, {"DISCOVERY_SECRET_KEY": env_key}, clear=False):
            resolved = discovery_crypto.resolve_discovery_secret_key_string()
        self.assertEqual(resolved, "")

    def test_resolve_prefers_django_over_env(self) -> None:
        django_key = Fernet.generate_key().decode("ascii")
        env_key = Fernet.generate_key().decode("ascii")
        with self.settings(DISCOVERY_SECRET_KEY=django_key):
            with patch.dict(os.environ, {"DISCOVERY_SECRET_KEY": env_key}, clear=False):
                resolved = discovery_crypto.resolve_discovery_secret_key_string()
        self.assertEqual(resolved, django_key)

    def test_build_fernet_from_settings_none_when_unset(self) -> None:
        with self.settings(DISCOVERY_SECRET_KEY=""):
            self.assertIsNone(discovery_crypto.build_fernet_from_settings())

    def test_resolve_uses_env_when_not_on_django_settings(self) -> None:
        key = Fernet.generate_key().decode("ascii")

        class _NoDiscoverySecret:
            pass

        fake = _NoDiscoverySecret()
        with patch("django_udp_discovery.crypto.django_settings", fake):
            with patch.dict(os.environ, {"DISCOVERY_SECRET_KEY": key}, clear=False):
                self.assertEqual(discovery_crypto.resolve_discovery_secret_key_string(), key)

    def test_build_fernet_from_settings_with_env_only(self) -> None:
        key = Fernet.generate_key().decode("ascii")

        class _NoDiscoverySecret:
            pass

        fake = _NoDiscoverySecret()
        with patch("django_udp_discovery.crypto.django_settings", fake):
            with patch.dict(os.environ, {"DISCOVERY_SECRET_KEY": key}, clear=False):
                f = discovery_crypto.build_fernet_from_settings()
        self.assertIsNotNone(f)
        self.assertEqual(
            discovery_crypto.decrypt_bytes(discovery_crypto.encrypt_bytes(b"ping", f), f),
            b"ping",
        )

    def test_get_validated_key_bytes_invalid_raises_without_echoing_secret(self) -> None:
        bad = "not-a-valid-fernet-key!!!!"
        with self.settings(DISCOVERY_SECRET_KEY=bad):
            with self.assertRaises(ValueError) as ctx:
                discovery_crypto.get_validated_key_bytes_from_settings()
        self.assertNotIn(bad, str(ctx.exception))


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

        Backward compatibility (6): with ``DISCOVERY_ENCRYPTION_ENABLED`` False
        (default), plain UDP request bytes and plain text responses are unchanged.
        
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

    def test_encrypted_discovery_roundtrip(self) -> None:
        """
        End-to-end encrypted discovery (1)(2)(4)(5):

        1. Client-style encrypted request: ``encrypt(DISCOVERY_MESSAGE)``.
        2. Server decrypts and accepts when plaintext matches ``DISCOVERY_MESSAGE``.
        4. Server sends encrypted ``RESPONSE_PREFIX`` + IP.
        5. Client-style decrypt of response yields plaintext ``SERVER_IP:...``.
        """
        key = Fernet.generate_key().decode("ascii")
        with override_settings(
            DISCOVERY_PORT=9991,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            RESPONSE_PREFIX="SERVER_IP:",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=key,
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            try:
                f = Fernet(key.encode("ascii"))
                token = discovery_crypto.encrypt_bytes(b"DISCOVER_SERVER", f)
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.settimeout(2.0)
                client_socket.sendto(token, ("127.0.0.1", 9991))
                response, _addr = client_socket.recvfrom(4096)
                client_socket.close()
                plain = discovery_crypto.decrypt_bytes(response, f)
                self.assertIsNotNone(plain)
                assert plain is not None
                self.assertTrue(plain.startswith(b"SERVER_IP:"))
            finally:
                stop_udp_service()
            time.sleep(0.15)
            self.assertFalse(is_running())

    def test_encrypted_mode_ignores_plaintext_discovery(self) -> None:
        """When encryption is on, raw discovery bytes are not accepted (invalid packet)."""
        key = Fernet.generate_key().decode("ascii")
        with override_settings(
            DISCOVERY_PORT=9990,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=key,
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.settimeout(0.5)
                client_socket.sendto(b"DISCOVER_SERVER", ("127.0.0.1", 9990))
                with self.assertRaises(socket.timeout):
                    client_socket.recvfrom(4096)
                client_socket.close()
            finally:
                stop_udp_service()

    def test_encrypted_mode_ignores_garbage_without_crash(self) -> None:
        """Malformed UDP payloads are ignored while the listener keeps running."""
        key = Fernet.generate_key().decode("ascii")
        with override_settings(
            DISCOVERY_PORT=9989,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=key,
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.settimeout(0.3)
                for _ in range(5):
                    client_socket.sendto(b"\xffnot-fernet\x00", ("127.0.0.1", 9989))
                self.assertTrue(is_running())
                client_socket.close()
            finally:
                stop_udp_service()

    def test_encryption_enabled_without_secret_stops_listener(self) -> None:
        """Encrypted mode requires a key; misconfiguration exits the worker."""
        env_backup = os.environ.pop("DISCOVERY_SECRET_KEY", None)
        try:
            with override_settings(
                DISCOVERY_PORT=9988,
                DISCOVERY_ENCRYPTION_ENABLED=True,
                DISCOVERY_SECRET_KEY="",
                ENABLE_LOGGING=False,
            ):
                start_udp_service()
                time.sleep(0.45)
                self.assertFalse(is_running())
        finally:
            if env_backup is not None:
                os.environ["DISCOVERY_SECRET_KEY"] = env_backup

    def test_encryption_enabled_with_invalid_secret_stops_listener(self) -> None:
        with override_settings(
            DISCOVERY_PORT=9987,
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY="not-a-valid-fernet-key",
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.45)
            self.assertFalse(is_running())

    def test_encrypted_listener_ignores_token_encrypted_with_wrong_key(self) -> None:
        """
        Invalid encrypted packet (3): Fernet token produced with a different key
        cannot be decrypted by the server; no response is sent.
        """
        server_key = Fernet.generate_key().decode("ascii")
        wrong_key = Fernet.generate_key().decode("ascii")
        with override_settings(
            DISCOVERY_PORT=9970,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=server_key,
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            try:
                wrong_f = Fernet(wrong_key.encode("ascii"))
                token = wrong_f.encrypt(b"DISCOVER_SERVER")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.settimeout(0.5)
                client_socket.sendto(token, ("127.0.0.1", 9970))
                with self.assertRaises(socket.timeout):
                    client_socket.recvfrom(4096)
                client_socket.close()
            finally:
                stop_udp_service()

    def test_encrypted_listener_ignores_valid_fernet_with_wrong_plaintext(self) -> None:
        """
        Invalid encrypted packet (3): decrypt succeeds but plaintext must equal
        ``DISCOVERY_MESSAGE`` exactly; otherwise the listener ignores the datagram.
        """
        key = Fernet.generate_key().decode("ascii")
        with override_settings(
            DISCOVERY_PORT=9971,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=key,
            ENABLE_LOGGING=False,
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            try:
                f = Fernet(key.encode("ascii"))
                token = f.encrypt(b"NOT_THE_DISCOVERY_MESSAGE")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.settimeout(0.5)
                client_socket.sendto(token, ("127.0.0.1", 9971))
                with self.assertRaises(socket.timeout):
                    client_socket.recvfrom(4096)
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


def _flip_bit(token: bytes, byte_index: int, bit: int = 0) -> bytes:
    """Flip one bit in the decoded bytes of a Fernet token and re-encode it."""
    raw = bytearray(base64.urlsafe_b64decode(token))
    raw[byte_index] ^= 1 << bit
    return base64.urlsafe_b64encode(bytes(raw))


class DiscoveryCryptoHardeningTest(SimpleTestCase):
    """TTL, tamper detection, replay cache and request parsing (no UDP)."""

    def setUp(self) -> None:
        self.fernet = Fernet(Fernet.generate_key())

    def test_defaults(self) -> None:
        self.assertEqual(discovery_crypto.DEFAULT_TOKEN_TTL, 30.0)
        self.assertEqual(discovery_crypto.DEFAULT_CLOCK_SKEW, 10.0)
        self.assertEqual(discovery_settings.DISCOVERY_ENCRYPTION_TTL, 30.0)
        self.assertEqual(discovery_settings.DISCOVERY_ENCRYPTION_CLOCK_SKEW, 10.0)
        self.assertEqual(discovery_settings.DISCOVERY_REPLAY_CACHE_SIZE, 10000)

    def test_expired_token_rejected(self) -> None:
        now = 1_700_000_000
        token = self.fernet.encrypt_at_time(b"x", now - 41)
        self.assertIsNone(
            discovery_crypto.decrypt_bytes(token, self.fernet, ttl=30, clock_skew=10, now=now)
        )

    def test_token_within_ttl_plus_skew_accepted(self) -> None:
        now = 1_700_000_000
        token = self.fernet.encrypt_at_time(b"x", now - 39)
        self.assertEqual(
            discovery_crypto.decrypt_bytes(token, self.fernet, ttl=30, clock_skew=10, now=now),
            b"x",
        )

    def test_future_token_skew_bounds(self) -> None:
        now = 1_700_000_000
        ok = self.fernet.encrypt_at_time(b"x", now + 10)
        too_far = self.fernet.encrypt_at_time(b"x", now + 11)
        self.assertEqual(
            discovery_crypto.decrypt_bytes(ok, self.fernet, ttl=30, clock_skew=10, now=now),
            b"x",
        )
        self.assertIsNone(
            discovery_crypto.decrypt_bytes(too_far, self.fernet, ttl=30, clock_skew=10, now=now)
        )

    def test_default_ttl_enforced(self) -> None:
        old = self.fernet.encrypt_at_time(b"x", int(time.time()) - 300)
        self.assertIsNone(discovery_crypto.decrypt_bytes(old, self.fernet))
        self.assertEqual(discovery_crypto.decrypt_bytes(old, self.fernet, ttl=None), b"x")

    def test_bit_flipped_real_token_rejected(self) -> None:
        token = self.fernet.encrypt(b"DISCOVER_SERVER|" + b"a" * 32)
        raw_len = len(base64.urlsafe_b64decode(token))
        # version, timestamp, IV, ciphertext and HMAC regions
        for index in (0, 1, 8, 9, 24, 30, raw_len - 1):
            with self.subTest(byte=index):
                tampered = _flip_bit(token, index)
                self.assertNotEqual(tampered, token)
                self.assertIsNone(discovery_crypto.decrypt_bytes(tampered, self.fernet))
                self.assertIsNone(
                    discovery_crypto.decrypt_bytes(tampered, self.fernet, ttl=None)
                )

    def test_replay_cache_detects_repeat_and_expires(self) -> None:
        cache = discovery_crypto.ReplayCache(ttl=50)
        fp = b"a" * 32
        self.assertTrue(cache.check_and_add(fp, now=100.0))
        self.assertFalse(cache.check_and_add(fp, now=149.0))
        # After the window the entry is pruned and the fingerprint is new again.
        self.assertTrue(cache.check_and_add(fp, now=151.0))

    def test_replay_cache_is_size_bounded(self) -> None:
        cache = discovery_crypto.ReplayCache(ttl=1000, max_entries=3)
        for i in range(5):
            self.assertTrue(cache.check_and_add(bytes([i]), now=1.0))
        self.assertEqual(len(cache), 3)
        self.assertFalse(cache.check_and_add(bytes([4]), now=2.0))

    def test_replay_cache_rejects_bad_params(self) -> None:
        with self.assertRaises(ValueError):
            discovery_crypto.ReplayCache(ttl=0)
        with self.assertRaises(ValueError):
            discovery_crypto.ReplayCache(ttl=10, max_entries=0)

    def test_fingerprint_ignores_base64_noise(self) -> None:
        token = self.fernet.encrypt(b"x")
        fp = discovery_crypto.token_fingerprint(token)
        self.assertIsNotNone(fp)
        # The base64 decoder skips characters outside the alphabet, so these
        # decrypt to the same token and must map to the same fingerprint.
        self.assertEqual(discovery_crypto.token_fingerprint(token + b"\n"), fp)
        self.assertEqual(discovery_crypto.token_fingerprint(token + b"!!"), fp)

    def test_parse_discovery_request(self) -> None:
        msg = b"DISCOVER_SERVER"
        nonce = b"0123456789abcdef0123456789abcdef"
        self.assertEqual(discovery_crypto.parse_discovery_request(msg, msg), (True, None))
        self.assertEqual(
            discovery_crypto.parse_discovery_request(msg + b"|" + nonce, msg), (True, nonce)
        )
        for bad in (
            b"DISCOVER_SERVERX",
            msg + b"|",
            msg + b"|short",
            msg + b"|" + nonce.upper(),
            msg + b"|" + nonce + b"|extra",
            msg + b"|" + b"a" * 129,
        ):
            with self.subTest(bad=bad):
                self.assertEqual(
                    discovery_crypto.parse_discovery_request(bad, msg), (False, None)
                )


class EncryptedListenerHardeningTest(TestCase):
    """UDP listener: nonce echo, replay rejection, expiry and tamper checks."""

    NONCE = b"00112233445566778899aabbccddeeff"

    def setUp(self) -> None:
        if is_running():
            stop_udp_service()
        time.sleep(0.1)
        self.key = Fernet.generate_key().decode("ascii")
        self.fernet = Fernet(self.key.encode("ascii"))

    def tearDown(self) -> None:
        if is_running():
            stop_udp_service()
        time.sleep(0.1)

    def _settings(self, port: int, **extra):
        values = dict(
            DISCOVERY_PORT=port,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            RESPONSE_PREFIX="SERVER_IP:",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            DISCOVERY_SECRET_KEY=self.key,
            ENABLE_LOGGING=False,
        )
        values.update(extra)
        return override_settings(**values)

    def _start(self) -> None:
        start_udp_service()
        time.sleep(0.35)
        self.assertTrue(is_running())

    def _exchange(self, port: int, packet: bytes, timeout: float = 1.0):
        """Send one packet; return the response bytes or None on timeout."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(packet, ("127.0.0.1", port))
            try:
                data, _ = sock.recvfrom(4096)
                return data
            except socket.timeout:
                return None
        finally:
            sock.close()

    def test_nonce_is_echoed_in_encrypted_response(self) -> None:
        with self._settings(9960):
            self._start()
            token = self.fernet.encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            response = self._exchange(9960, token)
            self.assertIsNotNone(response)
            plain = discovery_crypto.decrypt_bytes(response, self.fernet)
            self.assertIsNotNone(plain)
            body, _, nonce = plain.rpartition(b"|")
            self.assertTrue(body.startswith(b"SERVER_IP:"))
            self.assertEqual(nonce, self.NONCE)

    def test_legacy_request_without_nonce_gets_response_without_nonce(self) -> None:
        with self._settings(9961):
            self._start()
            response = self._exchange(9961, self.fernet.encrypt(b"DISCOVER_SERVER"))
            self.assertIsNotNone(response)
            plain = discovery_crypto.decrypt_bytes(response, self.fernet)
            self.assertTrue(plain.startswith(b"SERVER_IP:"))
            self.assertNotIn(b"|", plain)

    def test_replayed_request_is_ignored(self) -> None:
        with self._settings(9962):
            self._start()
            token = self.fernet.encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            self.assertIsNotNone(self._exchange(9962, token))
            self.assertIsNone(self._exchange(9962, token, timeout=0.5))
            # Same token with base64 noise appended is still a replay.
            self.assertIsNone(self._exchange(9962, token + b"\n", timeout=0.5))
            # A fresh token for the same request is answered.
            fresh = self.fernet.encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            self.assertIsNotNone(self._exchange(9962, fresh))
            self.assertTrue(is_running())

    def test_expired_request_is_ignored(self) -> None:
        with self._settings(9963):
            self._start()
            old = self.fernet.encrypt_at_time(
                b"DISCOVER_SERVER|" + self.NONCE, int(time.time()) - 60
            )
            self.assertIsNone(self._exchange(9963, old, timeout=0.5))

    def test_ttl_setting_is_honoured(self) -> None:
        with self._settings(9964, DISCOVERY_ENCRYPTION_TTL=120):
            self._start()
            aged = self.fernet.encrypt_at_time(
                b"DISCOVER_SERVER|" + self.NONCE, int(time.time()) - 60
            )
            self.assertIsNotNone(self._exchange(9964, aged))

    def test_future_request_beyond_skew_is_ignored(self) -> None:
        with self._settings(9965, DISCOVERY_ENCRYPTION_CLOCK_SKEW=5):
            self._start()
            future = self.fernet.encrypt_at_time(
                b"DISCOVER_SERVER|" + self.NONCE, int(time.time()) + 30
            )
            self.assertIsNone(self._exchange(9965, future, timeout=0.5))

    def test_bit_flipped_request_is_ignored(self) -> None:
        with self._settings(9966):
            self._start()
            token = self.fernet.encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            self.assertIsNone(self._exchange(9966, _flip_bit(token, 30), timeout=0.5))
            # The listener is unaffected, and the untouched token still works.
            self.assertIsNotNone(self._exchange(9966, token))

    def test_invalid_ttl_setting_stops_listener(self) -> None:
        for bad in ({"DISCOVERY_ENCRYPTION_TTL": 0},
                    {"DISCOVERY_ENCRYPTION_CLOCK_SKEW": -1},
                    {"DISCOVERY_REPLAY_CACHE_SIZE": 0},
                    {"DISCOVERY_ENCRYPTION_TTL": "soon"}):
            with self.subTest(setting=bad), self._settings(9967, **bad):
                start_udp_service()
                time.sleep(0.45)
                self.assertFalse(is_running())
                stop_udp_service()

    def test_plain_mode_ignores_ttl_settings(self) -> None:
        """Plain mode is unchanged: invalid encryption-only settings have no effect."""
        with self._settings(
            9968, DISCOVERY_ENCRYPTION_ENABLED=False, DISCOVERY_ENCRYPTION_TTL=0
        ):
            self._start()
            self.assertEqual(
                self._exchange(9968, b"DISCOVER_SERVER")[:10], b"SERVER_IP:"
            )


class KeyRotationTest(TestCase):
    """DISCOVERY_PREVIOUS_SECRET_KEYS: decrypt with old keys, always send with current."""

    NONCE = b"0123456789abcdef0123456789abcdef"

    def setUp(self) -> None:
        if is_running():
            stop_udp_service()
        time.sleep(0.1)
        self.old = Fernet.generate_key().decode("ascii")
        self.new = Fernet.generate_key().decode("ascii")

    def tearDown(self) -> None:
        if is_running():
            stop_udp_service()
        time.sleep(0.1)

    def _exchange(self, port: int, packet: bytes, timeout: float = 1.0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(packet, ("127.0.0.1", port))
            try:
                return sock.recvfrom(4096)[0]
            except socket.timeout:
                return None
        finally:
            sock.close()

    def _encrypted(self, port: int, **extra):
        values = dict(
            DISCOVERY_PORT=port,
            DISCOVERY_MESSAGE="DISCOVER_SERVER",
            RESPONSE_PREFIX="SERVER_IP:",
            DISCOVERY_ENCRYPTION_ENABLED=True,
            ENABLE_LOGGING=False,
        )
        values.update(extra)
        return override_settings(**values)

    # --- settings resolution -------------------------------------------------

    def test_previous_keys_from_settings_list_and_string(self) -> None:
        with override_settings(DISCOVERY_PREVIOUS_SECRET_KEYS=[self.old, " "]):
            self.assertEqual(discovery_crypto.resolve_previous_secret_keys(), [self.old])
        with override_settings(DISCOVERY_PREVIOUS_SECRET_KEYS=f"{self.old}, {self.new}"):
            self.assertEqual(
                discovery_crypto.resolve_previous_secret_keys(), [self.old, self.new]
            )

    def test_previous_keys_from_env(self) -> None:
        class _NoPreviousKeys:
            pass

        with patch("django_udp_discovery.crypto.django_settings", _NoPreviousKeys()):
            with patch.dict(os.environ, {"DISCOVERY_PREVIOUS_SECRET_KEYS": self.old}):
                self.assertEqual(discovery_crypto.resolve_previous_secret_keys(), [self.old])

    def test_keyring_from_settings(self) -> None:
        with override_settings(
            DISCOVERY_SECRET_KEY=self.new, DISCOVERY_PREVIOUS_SECRET_KEYS=[self.old]
        ):
            ring = discovery_crypto.build_keyring_from_settings()
        token = ring.encrypt(b"x")
        self.assertEqual(Fernet(self.new.encode()).decrypt(token), b"x")
        self.assertEqual(
            discovery_crypto.decrypt_bytes(Fernet(self.old.encode()).encrypt(b"y"), ring),
            b"y",
        )

    def test_keyring_errors(self) -> None:
        with override_settings(DISCOVERY_SECRET_KEY="", DISCOVERY_PREVIOUS_SECRET_KEYS=[self.old]):
            with self.assertRaises(ValueError):
                discovery_crypto.build_keyring_from_settings()
        with override_settings(DISCOVERY_SECRET_KEY=self.new, DISCOVERY_PREVIOUS_SECRET_KEYS=["bad"]):
            with self.assertRaises(ValueError):
                discovery_crypto.build_keyring_from_settings()
        with override_settings(DISCOVERY_SECRET_KEY=self.new, DISCOVERY_PREVIOUS_SECRET_KEYS=42):
            with self.assertRaises(ValueError):
                discovery_crypto.build_keyring_from_settings()
        with override_settings(DISCOVERY_SECRET_KEY=""):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("DISCOVERY_PREVIOUS_SECRET_KEYS", None)
                self.assertIsNone(discovery_crypto.build_keyring_from_settings())

    # --- listener ------------------------------------------------------------

    def test_server_accepts_old_key_and_replies_with_current(self) -> None:
        """Rotation step 2: server already on the new key, client still on the old."""
        with self._encrypted(
            9955, DISCOVERY_SECRET_KEY=self.new, DISCOVERY_PREVIOUS_SECRET_KEYS=[self.old]
        ):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            request = Fernet(self.old.encode()).encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            reply = self._exchange(9955, request)
            self.assertIsNotNone(reply)
            plain = Fernet(self.new.encode()).decrypt(reply)
            self.assertTrue(plain.endswith(b"|" + self.NONCE))

    def test_server_rejects_old_key_once_removed(self) -> None:
        """Rotation step 3: the old key is gone, so old-key requests get no reply."""
        with self._encrypted(9956, DISCOVERY_SECRET_KEY=self.new):
            start_udp_service()
            time.sleep(0.35)
            self.assertTrue(is_running())
            request = Fernet(self.old.encode()).encrypt(b"DISCOVER_SERVER|" + self.NONCE)
            self.assertIsNone(self._exchange(9956, request, timeout=0.5))

    def test_listener_refuses_bad_rotation_config(self) -> None:
        for extra in (
            {"DISCOVERY_SECRET_KEY": self.new, "DISCOVERY_PREVIOUS_SECRET_KEYS": ["bad"]},
            {"DISCOVERY_SECRET_KEY": "", "DISCOVERY_PREVIOUS_SECRET_KEYS": [self.old]},
        ):
            with self.subTest(extra=list(extra)), self._encrypted(9957, **extra):
                start_udp_service()
                time.sleep(0.45)
                self.assertFalse(is_running())
                stop_udp_service()


class AutostartDecisionTest(SimpleTestCase):
    """should_autostart(): which processes start the listener on Django load."""

    def _check(self, argv, environ=None):
        from django_udp_discovery.apps import should_autostart

        with patch.dict(sys.modules):
            sys.modules.pop("pytest", None)
            return should_autostart(argv=argv, environ=environ or {})

    def test_runserver_reloader_parent_does_not_start(self) -> None:
        self.assertFalse(self._check(["manage.py", "runserver"]))

    def test_runserver_serving_child_starts(self) -> None:
        self.assertTrue(self._check(["manage.py", "runserver"], {"RUN_MAIN": "true"}))

    def test_runserver_noreload_starts(self) -> None:
        self.assertTrue(self._check(["/srv/app/manage.py", "runserver", "--noreload"]))

    def test_other_commands_do_not_start(self) -> None:
        for argv in (
            ["manage.py", "migrate"],
            ["manage.py", "shell"],
            ["manage.py", "start_discovery"],
            ["/venv/bin/django-admin", "check"],
            ["/usr/lib/python3/site-packages/django/__main__.py", "migrate"],
            ["manage.py"],
        ):
            with self.subTest(argv=argv):
                self.assertFalse(self._check(argv, {"RUN_MAIN": "true"}))

    def test_test_command_does_not_start(self) -> None:
        self.assertFalse(self._check(["manage.py", "test"], {"RUN_MAIN": "true"}))

    def test_wsgi_asgi_servers_start(self) -> None:
        for argv in (["/venv/bin/gunicorn", "proj.wsgi"], ["uvicorn", "proj.asgi:app"]):
            with self.subTest(argv=argv):
                self.assertTrue(self._check(argv))

    @override_settings(DISCOVERY_AUTOSTART=False)
    def test_setting_disables_autostart(self) -> None:
        self.assertFalse(self._check(["/venv/bin/gunicorn", "proj.wsgi"]))
        self.assertFalse(self._check(["manage.py", "runserver", "--noreload"]))

    @override_settings(TESTING=True)
    def test_testing_setting_disables_autostart(self) -> None:
        self.assertFalse(self._check(["/venv/bin/gunicorn", "proj.wsgi"]))


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
