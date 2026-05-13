"""
Tests for UDP broadcast discovery functionality.

Tests the discover() and discover_one() functions with mocked sockets.
"""
import pytest
import socket
from unittest.mock import Mock, patch, MagicMock, call
from discovery_client import (
    ClientConfig,
    discover,
    discover_one,
    DiscoveryResult,
    load_config,
)
from discovery_client.network.socket import (
    create_discovery_socket,
    send_discovery_request,
    receive_responses,
    parse_response,
    discover_servers_single_broadcast,
    DEFAULT_BROADCAST_ADDRESS,
)


class TestParseResponse:
    """Tests for parse_response function."""
    
    def test_parse_valid_response_with_port(self):
        """Test parsing valid response with IP and port."""
        response = b"SERVER_IP:192.168.1.100:8000"
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is not None
        ip, port = result
        assert ip == "192.168.1.100"
        assert port == 8000
    
    def test_parse_valid_response_without_port(self):
        """Test parsing valid response without port (defaults to 8000)."""
        response = b"SERVER_IP:10.0.0.5"
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is not None
        ip, port = result
        assert ip == "10.0.0.5"
        assert port == 8000  # Default port
    
    def test_parse_invalid_prefix(self):
        """Test parsing response with wrong prefix."""
        response = b"WRONG_PREFIX:192.168.1.100:8000"
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is None
    
    def test_parse_invalid_ip_format(self):
        """Test parsing response with invalid IP format."""
        response = b"SERVER_IP:invalid:8000"
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is None
    
    def test_parse_invalid_port(self):
        """Test parsing response with invalid port."""
        response = b"SERVER_IP:192.168.1.100:99999"  # Port out of range
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is None
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        response = b"SERVER_IP:"
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is None
    
    def test_parse_response_with_whitespace(self):
        """Test parsing response with whitespace."""
        response = b"SERVER_IP:  192.168.1.100  :  8000  "
        prefix = b"SERVER_IP:"
        
        result = parse_response(response, prefix)
        
        assert result is not None
        ip, port = result
        assert ip == "192.168.1.100"
        assert port == 8000


class TestCreateDiscoverySocket:
    """Tests for create_discovery_socket function."""
    
    @patch('discovery_client.network.socket.socket.socket')
    def test_socket_creation_and_configuration(self, mock_socket_class):
        """Test that socket is created and configured correctly."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        
        timeout = 5.0
        sock = create_discovery_socket(timeout)
        
        # Verify socket creation
        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Verify SO_BROADCAST is set
        mock_sock.setsockopt.assert_any_call(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )
        
        # Verify timeout is set
        mock_sock.settimeout.assert_called_once_with(timeout)
        
        assert sock == mock_sock


class TestSendDiscoveryRequest:
    """Tests for send_discovery_request function."""
    
    def test_send_with_default_broadcast(self):
        """Test sending discovery request with default broadcast address."""
        mock_sock = MagicMock()
        message = b"DISCOVER_SERVER"
        port = 9999
        
        send_discovery_request(mock_sock, message, port)
        
        mock_sock.sendto.assert_called_once_with(
            message,
            (DEFAULT_BROADCAST_ADDRESS, port)
        )
    
    def test_send_with_custom_broadcast(self):
        """Test sending discovery request with custom broadcast address."""
        mock_sock = MagicMock()
        message = b"DISCOVER_SERVER"
        port = 8888
        broadcast = "192.168.1.255"
        
        send_discovery_request(mock_sock, message, port, broadcast)
        
        mock_sock.sendto.assert_called_once_with(
            message,
            (broadcast, port)
        )


class TestReceiveResponses:
    """Tests for receive_responses function."""
    
    def test_receive_valid_responses(self):
        """Test receiving and parsing valid responses."""
        mock_sock = MagicMock()
        
        # Mock recvfrom to return valid responses then timeout
        responses = [
            (b"SERVER_IP:192.168.1.100:8000", ("192.168.1.100", 12345)),
            (b"SERVER_IP:10.0.0.5:9000", ("10.0.0.5", 12346)),
        ]
        mock_sock.recvfrom.side_effect = responses + [socket.timeout]
        
        config = ClientConfig()
        results = receive_responses(mock_sock, config)
        
        assert len(results) == 2
        assert results[0].ip == "192.168.1.100"
        assert results[0].port == 8000
        assert results[1].ip == "10.0.0.5"
        assert results[1].port == 9000
    
    def test_receive_invalid_responses_ignored(self):
        """Test that invalid responses are ignored."""
        mock_sock = MagicMock()
        
        # Mix of valid and invalid responses
        responses = [
            (b"WRONG_PREFIX:192.168.1.100:8000", ("192.168.1.100", 12345)),
            (b"SERVER_IP:10.0.0.5:9000", ("10.0.0.5", 12346)),
            (b"INVALID", ("192.168.1.101", 12347)),
        ]
        mock_sock.recvfrom.side_effect = responses + [socket.timeout]
        
        config = ClientConfig()
        results = receive_responses(mock_sock, config)
        
        # Only valid response should be included
        assert len(results) == 1
        assert results[0].ip == "10.0.0.5"
        assert results[0].port == 9000
    
    def test_receive_timeout_returns_empty(self):
        """Test that timeout returns empty list."""
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout
        
        config = ClientConfig()
        results = receive_responses(mock_sock, config)
        
        assert len(results) == 0
    
    def test_receive_max_responses(self):
        """Test that max_responses limit is respected."""
        mock_sock = MagicMock()
        
        # Return multiple valid responses
        responses = [
            (b"SERVER_IP:192.168.1.100:8000", ("192.168.1.100", 12345)),
            (b"SERVER_IP:10.0.0.5:9000", ("10.0.0.5", 12346)),
            (b"SERVER_IP:172.16.0.1:7000", ("172.16.0.1", 12347)),
        ]
        mock_sock.recvfrom.side_effect = responses
        
        config = ClientConfig()
        results = receive_responses(mock_sock, config, max_responses=2)
        
        assert len(results) == 2


class TestDiscoverServersSingleBroadcast:
    """Tests for discover_servers_single_broadcast function."""
    
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_full_discovery_flow(self, mock_receive, mock_send, mock_create_socket):
        """Test complete discovery flow."""
        # Setup mocks
        mock_sock = MagicMock()
        mock_create_socket.return_value = mock_sock
        
        mock_results = [
            DiscoveryResult(
                ip="192.168.1.100",
                port=8000,
                raw_response=b"SERVER_IP:192.168.1.100:8000"
            )
        ]
        mock_receive.return_value = mock_results
        
        config = ClientConfig(
            discovery_message=b"DISCOVER_SERVER",
            discovery_port=9999,
            timeout=5.0
        )
        
        # Execute
        results = discover_servers_single_broadcast(config)
        
        # Verify
        mock_create_socket.assert_called_once_with(5.0)
        mock_send.assert_called_once_with(
            mock_sock,
            b"DISCOVER_SERVER",
            9999,
            DEFAULT_BROADCAST_ADDRESS
        )
        # max_responses is optional and defaults to None
        mock_receive.assert_called_once_with(mock_sock, config)
        mock_sock.close.assert_called_once()
        
        assert len(results) == 1
        assert results[0].ip == "192.168.1.100"
    
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_discovery_with_timeout(self, mock_receive, mock_send, mock_create_socket):
        """Test discovery when no responses (timeout)."""
        mock_sock = MagicMock()
        mock_create_socket.return_value = mock_sock
        mock_receive.return_value = []  # No responses
        
        config = ClientConfig(timeout=2.0)
        results = discover_servers_single_broadcast(config)
        
        assert len(results) == 0
        mock_sock.close.assert_called_once()
    
    @patch('discovery_client.network.socket.create_discovery_socket')
    def test_discovery_socket_error(self, mock_create_socket):
        """Test discovery when socket creation fails."""
        mock_create_socket.side_effect = OSError("Socket creation failed")
        
        config = ClientConfig()
        
        with pytest.raises(OSError):
            discover_servers_single_broadcast(config)


class TestDiscoverFunction:
    """Tests for discover() function."""
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_with_default_config(self, mock_discover):
        """Test discover() with default configuration."""
        mock_results = [
            DiscoveryResult(
                ip="192.168.1.100",
                port=8000,
                raw_response=b"SERVER_IP:192.168.1.100:8000"
            )
        ]
        mock_discover.return_value = mock_results
        
        results = discover()
        
        assert len(results) == 1
        assert results[0].ip == "192.168.1.100"
        mock_discover.assert_called_once()
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_with_custom_config(self, mock_discover):
        """Test discover() with custom configuration."""
        config = ClientConfig(timeout=10.0, discovery_port=8888)
        mock_discover.return_value = []
        
        results = discover(config=config)
        
        assert len(results) == 0
        mock_discover.assert_called_once_with(config)
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_socket_error_returns_empty(self, mock_discover):
        """Test that socket errors return empty list."""
        mock_discover.side_effect = OSError("Network error")
        
        results = discover()
        
        assert len(results) == 0


class TestDiscoverOneFunction:
    """Tests for discover_one() function."""
    
    @patch('discovery_client.discover')
    def test_discover_one_returns_first_result(self, mock_discover):
        """Test discover_one() returns first result."""
        mock_results = [
            DiscoveryResult(
                ip="192.168.1.100",
                port=8000,
                raw_response=b"SERVER_IP:192.168.1.100:8000"
            ),
            DiscoveryResult(
                ip="10.0.0.5",
                port=9000,
                raw_response=b"SERVER_IP:10.0.0.5:9000"
            ),
        ]
        mock_discover.return_value = mock_results
        
        result = discover_one()
        
        assert result is not None
        assert result.ip == "192.168.1.100"
        assert result.port == 8000
        mock_discover.assert_called_once()
    
    @patch('discovery_client.discover')
    def test_discover_one_returns_none_when_empty(self, mock_discover):
        """Test discover_one() returns None when no servers found."""
        mock_discover.return_value = []
        
        result = discover_one()
        
        assert result is None
        mock_discover.assert_called_once()
    
    @patch('discovery_client.discover')
    def test_discover_one_with_custom_config(self, mock_discover):
        """Test discover_one() with custom configuration."""
        config = ClientConfig(timeout=10.0)
        mock_discover.return_value = []
        
        result = discover_one(config=config)
        
        assert result is None
        mock_discover.assert_called_once_with(config=config)


class TestIntegration:
    """Integration tests for discovery."""
    
    @patch('discovery_client.network.socket.socket.socket')
    def test_end_to_end_discovery(self, mock_socket_class):
        """Test end-to-end single-broadcast discovery with mocked socket."""
        # Setup mock socket
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        
        # Mock recvfrom to return one valid response then timeout
        mock_sock.recvfrom.side_effect = [
            (b"SERVER_IP:192.168.1.100:8000", ("192.168.1.100", 12345)),
            socket.timeout,
        ]
        
        config = ClientConfig(
            discovery_message=b"DISCOVER_SERVER",
            discovery_port=9999,
            timeout=5.0,
            response_prefix=b"SERVER_IP:"
        )
        
        results = discover_servers_single_broadcast(config)
        
        # Verify socket was configured correctly
        mock_sock.setsockopt.assert_any_call(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )
        mock_sock.settimeout.assert_called_once_with(5.0)
        
        # Verify sendto was called correctly
        mock_sock.sendto.assert_called_once_with(
            b"DISCOVER_SERVER",
            (DEFAULT_BROADCAST_ADDRESS, 9999)
        )
        
        # Verify results
        assert len(results) == 1
        assert results[0].ip == "192.168.1.100"
        assert results[0].port == 8000
        assert results[0].raw_response == b"SERVER_IP:192.168.1.100:8000"
        
        # Verify socket was closed
        mock_sock.close.assert_called_once()
