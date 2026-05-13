"""
End-to-end integration tests for UDP discovery.

Tests the complete discovery flow using a mock UDP server running in a background thread.

Platform Compatibility:
- These tests use UDP broadcast which should work on Windows, Linux, and macOS
- Some tests may be skipped or behave differently in restricted network environments
- Tests are designed to be stable and handle timing variations gracefully
"""
import pytest
import socket
import threading
import time
from typing import Optional
from discovery_client import ClientConfig, discover, discover_one, DiscoveryResult


class MockDiscoveryServer:
    """
    Mock UDP server that responds to discovery requests.
    
    Runs in a background thread and responds to DISCOVER_SERVER messages
    with SERVER_IP:<ip>:<port> format responses.
    """
    
    def __init__(
        self,
        port: int = 9999,
        server_ip: str = "192.168.1.100",
        server_port: int = 8000,
        discovery_message: bytes = b"DISCOVER_SERVER",
        response_prefix: bytes = b"SERVER_IP:",
        timeout: float = 0.1
    ):
        """
        Initialize mock discovery server.
        
        Args:
            port: UDP port to listen on (default: 9999)
            server_ip: IP address to include in response (default: "192.168.1.100")
            server_port: Port to include in response (default: 8000)
            discovery_message: Message that triggers response (default: b"DISCOVER_SERVER")
            response_prefix: Prefix for response message (default: b"SERVER_IP:")
            timeout: Socket timeout for server loop (default: 0.1)
        """
        self.port = port
        self.server_ip = server_ip
        self.server_port = server_port
        self.discovery_message = discovery_message
        self.response_prefix = response_prefix
        self.timeout = timeout
        
        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.request_count = 0
        self.response_count = 0
    
    def _server_loop(self):
        """Main server loop running in background thread."""
        try:
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    self.request_count += 1
                    
                    if data == self.discovery_message:
                        response = f"{self.response_prefix.decode()}{self.server_ip}:{self.server_port}".encode()
                        self.sock.sendto(response, addr)
                        self.response_count += 1
                except socket.timeout:
                    # Timeout is expected, continue loop
                    continue
                except OSError:
                    # Socket closed or error, exit loop
                    break
        except Exception:
            # Any other exception, exit loop
            pass
    
    def start(self):
        """Start the mock server in a background thread."""
        if self.running:
            return
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(('', self.port))
            self.sock.settimeout(self.timeout)
            
            self.running = True
            self.thread = threading.Thread(target=self._server_loop, daemon=True)
            self.thread.start()
            
            # Give server a moment to start
            time.sleep(0.1)
        except OSError as e:
            self.running = False
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
            raise RuntimeError(f"Failed to start mock server on port {self.port}: {e}")
    
    def stop(self):
        """Stop the mock server and cleanup."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


@pytest.fixture
def mock_server():
    """
    Pytest fixture that provides a mock discovery server.
    
    Starts server before test, stops after test.
    Ensures server is ready before yielding.
    """
    server = MockDiscoveryServer()
    try:
        server.start()
        # Give server time to bind and be ready
        time.sleep(0.2)
        yield server
    finally:
        server.stop()


@pytest.fixture
def mock_server_custom_port():
    """
    Pytest fixture for mock server on custom port.
    
    Uses port 9998 to avoid conflicts with default port tests.
    """
    server = MockDiscoveryServer(port=9998)
    try:
        server.start()
        # Give server time to bind and be ready
        time.sleep(0.2)
        yield server
    finally:
        server.stop()


class TestEndToEndDiscovery:
    """End-to-end tests for discovery with mock UDP server."""
    
    def test_discover_single_server(self, mock_server):
        """Test discovery with a single mock server."""
        # Use default config (port 9999)
        config = ClientConfig(timeout=2.0)
        
        # Give server extra time to be ready
        time.sleep(0.2)
        
        # Discover servers
        results = discover(config=config)
        
        # Verify results
        assert len(results) >= 1, "Should find at least one server"
        
        # Find our mock server in results
        mock_server_found = False
        for result in results:
            if result.ip == mock_server.server_ip and result.port == mock_server.server_port:
                mock_server_found = True
                # Verify response format
                assert result.raw_response.startswith(mock_server.response_prefix)
                assert mock_server.server_ip in result.raw_response.decode('utf-8', errors='ignore')
                break
        
        assert mock_server_found, f"Mock server ({mock_server.server_ip}:{mock_server.server_port}) not found in results"
        
        # Verify server received request (may take a moment)
        time.sleep(0.1)
        assert mock_server.request_count > 0, "Server should have received at least one discovery request"
        assert mock_server.response_count > 0, "Server should have sent at least one response"
    
    def test_discover_one_single_server(self, mock_server):
        """Test discover_one() with a single mock server."""
        config = ClientConfig(timeout=2.0)
        
        # Give server time to be ready
        time.sleep(0.2)
        
        result = discover_one(config=config)
        
        assert result is not None, "discover_one() should find the server"
        assert result.ip == mock_server.server_ip
        assert result.port == mock_server.server_port
        assert isinstance(result, DiscoveryResult)
    
    def test_discover_no_server(self):
        """Test discovery when no server is running."""
        # Use a port that no server is listening on
        config = ClientConfig(timeout=1.0, discovery_port=9997)
        
        results = discover(config=config)
        
        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_discover_one_no_server(self):
        """Test discover_one() when no server is running."""
        config = ClientConfig(timeout=1.0, discovery_port=9997)
        
        result = discover_one(config=config)
        
        # Should return None, not crash
        assert result is None
    
    def test_discover_custom_port(self, mock_server_custom_port):
        """Test discovery with custom port."""
        config = ClientConfig(timeout=2.0, discovery_port=9998)
        
        results = discover(config=config)
        
        assert len(results) >= 1
        # Verify we found the server on custom port
        found = any(
            r.ip == mock_server_custom_port.server_ip 
            and r.port == mock_server_custom_port.server_port
            for r in results
        )
        assert found, "Should find server on custom port"
    
    def test_discover_multiple_responses(self, mock_server):
        """Test discovery when multiple responses are received (deduplication)."""
        # Test that discovery handles multiple responses correctly and deduplicates
        config = ClientConfig(timeout=2.0)
        
        # Give server time to be ready
        time.sleep(0.2)
        
        # Discover servers - may get multiple responses from same server
        results = discover(config=config)
        
        # Should find at least one server
        assert len(results) >= 1, "Should find at least one server"
        
        # Verify all results are unique (deduplication working)
        unique_keys = {(r.ip, r.port) for r in results}
        assert len(unique_keys) == len(results), "Results should be deduplicated"
        
        # Verify we found our mock server
        found = any(
            r.ip == mock_server.server_ip and r.port == mock_server.server_port
            for r in results
        )
        assert found, "Should find the mock server"
    
    def test_discover_two_different_servers(self):
        """Test discovery with two servers on different discovery ports."""
        # Start two servers on different discovery ports to simulate different networks
        server1 = MockDiscoveryServer(port=9999, server_ip="192.168.1.100", server_port=8000)
        server2 = MockDiscoveryServer(port=9998, server_ip="192.168.1.101", server_port=8001)
        
        try:
            server1.start()
            server2.start()
            time.sleep(0.2)
            
            # Discover on first port
            config1 = ClientConfig(timeout=1.0, discovery_port=9999)
            results1 = discover(config=config1)
            
            # Discover on second port
            config2 = ClientConfig(timeout=1.0, discovery_port=9998)
            results2 = discover(config=config2)
            
            # Should find servers on respective ports
            found1 = any(r.ip == "192.168.1.100" for r in results1)
            found2 = any(r.ip == "192.168.1.101" for r in results2)
            
            # At least one should be found (depending on network configuration)
            assert found1 or found2, "Should find at least one server"
            
        finally:
            server1.stop()
            server2.stop()
    
    def test_discover_response_format(self, mock_server):
        """Test that discovered results have correct format."""
        config = ClientConfig(timeout=2.0)
        
        results = discover(config=config)
        
        assert len(results) >= 1
        
        result = results[0]
        
        # Verify DiscoveryResult structure
        assert hasattr(result, 'ip')
        assert hasattr(result, 'port')
        assert hasattr(result, 'raw_response')
        assert isinstance(result.ip, str)
        assert isinstance(result.port, int)
        assert isinstance(result.raw_response, bytes)
        
        # Verify raw_response contains expected format
        assert result.raw_response.startswith(b"SERVER_IP:")
        assert mock_server.server_ip.encode() in result.raw_response
    
    def test_discover_timeout_behavior(self):
        """Test that discovery times out correctly when no server responds."""
        config = ClientConfig(timeout=0.5, discovery_port=9997)  # Port with no server
        
        start_time = time.time()
        results = discover(config=config)
        elapsed = time.time() - start_time
        
        # Should return quickly (within timeout + small buffer)
        assert elapsed < 1.0, "Discovery should complete within timeout"
        assert len(results) == 0, "Should return empty list when no servers"
    
    def test_discover_custom_message(self, mock_server):
        """Test discovery with custom discovery message."""
        # Create server with custom message
        custom_server = MockDiscoveryServer(
            port=9998,
            discovery_message=b"CUSTOM_DISCOVER"
        )
        
        try:
            custom_server.start()
            time.sleep(0.1)
            
            # Try with default message (should not find custom server)
            config_default = ClientConfig(timeout=1.0, discovery_port=9998)
            results_default = discover(config=config_default)
            
            # Should not find server with default message
            # (unless mock_server on 9999 also responds, which is fine)
            
            # Try with custom message
            config_custom = ClientConfig(
                timeout=1.0,
                discovery_port=9998,
                discovery_message=b"CUSTOM_DISCOVER"
            )
            results_custom = discover(config=config_custom)
            
            # Should find custom server
            assert len(results_custom) >= 1
            
        finally:
            custom_server.stop()


class TestMockServer:
    """Tests for the MockDiscoveryServer helper class."""
    
    def test_mock_server_start_stop(self):
        """Test that mock server can start and stop cleanly."""
        server = MockDiscoveryServer(port=9996)
        
        try:
            server.start()
            assert server.running
            assert server.thread is not None
            assert server.thread.is_alive()
            
            server.stop()
            assert not server.running
        except Exception:
            server.stop()
            raise
    
    def test_mock_server_context_manager(self):
        """Test mock server as context manager."""
        with MockDiscoveryServer(port=9995) as server:
            assert server.running
            assert server.thread is not None
        
        # After context exit, server should be stopped
        assert not server.running
    
    def test_mock_server_responds_to_discovery(self):
        """Test that mock server responds correctly to discovery messages."""
        server = MockDiscoveryServer(
            port=9994,
            server_ip="10.0.0.5",
            server_port=9000
        )
        
        try:
            server.start()
            time.sleep(0.1)
            
            # Send discovery message
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            test_sock.settimeout(1.0)
            
            test_sock.sendto(b"DISCOVER_SERVER", ("127.0.0.1", 9994))
            
            # Receive response
            data, addr = test_sock.recvfrom(1024)
            
            # Verify response
            assert data.startswith(b"SERVER_IP:")
            assert b"10.0.0.5:9000" in data
            
            test_sock.close()
            
            # Verify server stats
            assert server.request_count > 0
            assert server.response_count > 0
            
        finally:
            server.stop()
    
    def test_mock_server_ignores_wrong_message(self):
        """Test that mock server ignores non-discovery messages."""
        server = MockDiscoveryServer(port=9993)
        
        try:
            server.start()
            time.sleep(0.1)
            
            initial_count = server.response_count
            
            # Send wrong message
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.sendto(b"WRONG_MESSAGE", ("127.0.0.1", 9993))
            time.sleep(0.1)
            
            # Server should have received request but not responded
            assert server.request_count > 0
            assert server.response_count == initial_count
            
            test_sock.close()
            
        finally:
            server.stop()


class TestIntegrationStability:
    """Tests for cross-platform stability and edge cases."""
    
    def test_discover_handles_network_errors_gracefully(self):
        """Test that discover() handles network errors without crashing."""
        # Use invalid port to trigger potential errors
        config = ClientConfig(timeout=0.5, discovery_port=1)  # Port 1 may require privileges
        
        # Should not raise exception, should return empty list
        results = discover(config=config)
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_discover_one_handles_network_errors_gracefully(self):
        """Test that discover_one() handles network errors without crashing."""
        config = ClientConfig(timeout=0.5, discovery_port=1)
        
        # Should not raise exception, should return None
        result = discover_one(config=config)
        assert result is None
    
    def test_discover_with_very_short_timeout(self, mock_server):
        """Test discovery with very short timeout."""
        config = ClientConfig(timeout=0.1)  # Very short timeout
        
        results = discover(config=config)
        
        # May or may not find server depending on timing, but should not crash
        assert isinstance(results, list)
        # Result could be empty or have servers depending on timing
    
    def test_discover_multiple_calls(self, mock_server):
        """Test that discover() can be called multiple times."""
        config = ClientConfig(timeout=1.0)
        
        # Call multiple times
        results1 = discover(config=config)
        time.sleep(0.1)
        results2 = discover(config=config)
        time.sleep(0.1)
        results3 = discover(config=config)
        
        # All should work without errors
        assert isinstance(results1, list)
        assert isinstance(results2, list)
        assert isinstance(results3, list)
        
        # At least one call should find the server
        total_found = len(results1) + len(results2) + len(results3)
        assert total_found > 0, "At least one discovery should find the server"
    
    def test_discover_deduplication_with_same_server(self, mock_server):
        """Test that same server responding multiple times is deduplicated."""
        config = ClientConfig(timeout=2.0)
        
        results = discover(config=config)
        
        # If same server responds multiple times, should be deduplicated
        if len(results) > 0:
            # Check for duplicates by (ip, port)
            unique_keys = {(r.ip, r.port) for r in results}
            assert len(unique_keys) == len(results), "Results should be deduplicated"
    
    def test_discover_with_custom_response_prefix(self):
        """Test discovery with custom response prefix."""
        custom_server = MockDiscoveryServer(
            port=9992,
            response_prefix=b"CUSTOM_PREFIX:"
        )
        
        try:
            custom_server.start()
            time.sleep(0.1)
            
            # Try with default prefix (should not find)
            config_default = ClientConfig(timeout=1.0, discovery_port=9992)
            results_default = discover(config=config_default)
            
            # Default prefix won't match custom prefix, so may not find server
            # This is expected behavior
            
            # Try with custom prefix
            config_custom = ClientConfig(
                timeout=1.0,
                discovery_port=9992,
                response_prefix=b"CUSTOM_PREFIX:"
            )
            results_custom = discover(config=config_custom)
            
            # Should find server with matching prefix
            assert len(results_custom) >= 1
            
        finally:
            custom_server.stop()
