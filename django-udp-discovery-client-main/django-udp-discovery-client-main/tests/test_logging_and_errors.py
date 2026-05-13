"""
Tests for logging and error handling in discovery functions.

Tests that errors are handled gracefully and logged appropriately.
"""
import pytest
import socket
import logging
from unittest.mock import Mock, patch, MagicMock
from discovery_client import ClientConfig, discover, discover_one
from discovery_client.network.socket import (
    create_discovery_socket,
    send_discovery_request,
    receive_responses,
    discover_servers_multi_interface,
    get_interface_broadcast,
)
from discovery_client.network.interfaces import InterfaceInfo
from discovery_client.results import DiscoveryResult


class TestSocketCreationLogging:
    """Tests for logging in socket creation."""
    
    @patch('discovery_client.network.socket.socket.socket')
    def test_socket_creation_logs_info(self, mock_socket_class, caplog):
        """Test that socket creation is logged."""
        with caplog.at_level(logging.DEBUG):
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            
            create_discovery_socket(5.0)
            
            # Check for debug logs
            assert any("Creating UDP discovery socket" in record.message for record in caplog.records)
            assert any("Socket broadcast enabled" in record.message for record in caplog.records)
            assert any("Socket timeout set" in record.message for record in caplog.records)
    
    @patch('discovery_client.network.socket.socket.socket')
    def test_socket_creation_error_logged(self, mock_socket_class, caplog):
        """Test that socket creation errors are logged."""
        with caplog.at_level(logging.ERROR):
            mock_socket_class.side_effect = OSError("Permission denied")
            
            with pytest.raises(OSError):
                create_discovery_socket(5.0)
            
            # Check for error log
            assert any("Failed to create discovery socket" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)


class TestSendDiscoveryRequestLogging:
    """Tests for logging in send_discovery_request."""
    
    def test_send_logs_info(self, caplog):
        """Test that sending discovery request is logged."""
        with caplog.at_level(logging.INFO):
            mock_sock = MagicMock()
            
            send_discovery_request(mock_sock, b"DISCOVER_SERVER", 9999, "255.255.255.255")
            
            # Check for info log
            assert any("Sending discovery request" in record.message for record in caplog.records)
            assert any("255.255.255.255:9999" in record.message for record in caplog.records)
    
    def test_send_error_logged(self, caplog):
        """Test that send errors are logged."""
        with caplog.at_level(logging.ERROR):
            mock_sock = MagicMock()
            mock_sock.sendto.side_effect = OSError("Network unreachable")
            
            with pytest.raises(OSError):
                send_discovery_request(mock_sock, b"DISCOVER_SERVER", 9999)
            
            # Check for error log
            assert any("Failed to send discovery request" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)


class TestReceiveResponsesLogging:
    """Tests for logging in receive_responses."""
    
    def test_receive_valid_response_logged(self, caplog):
        """Test that valid responses are logged."""
        with caplog.at_level(logging.INFO):
            mock_sock = MagicMock()
            mock_sock.recvfrom.side_effect = [
                (b"SERVER_IP:192.168.1.100:8000", ("192.168.1.100", 12345)),
                socket.timeout,
            ]
            
            config = ClientConfig()
            results = receive_responses(mock_sock, config)
            
            # Check for info logs
            assert any("Parsed valid response" in record.message for record in caplog.records)
            assert any("192.168.1.100:8000" in record.message for record in caplog.records)
            assert any("Discovery complete" in record.message for record in caplog.records)
    
    def test_receive_invalid_response_logged(self, caplog):
        """Test that invalid responses are logged as warnings."""
        with caplog.at_level(logging.WARNING):
            mock_sock = MagicMock()
            mock_sock.recvfrom.side_effect = [
                (b"INVALID_RESPONSE", ("192.168.1.100", 12345)),
                socket.timeout,
            ]
            
            config = ClientConfig()
            results = receive_responses(mock_sock, config)
            
            # Check for warning log
            assert any("Received invalid response" in record.message for record in caplog.records)
            assert any(record.levelname == "WARNING" for record in caplog.records)
    
    def test_receive_timeout_logged(self, caplog):
        """Test that timeout is logged."""
        with caplog.at_level(logging.INFO):
            mock_sock = MagicMock()
            mock_sock.recvfrom.side_effect = socket.timeout
            
            config = ClientConfig()
            results = receive_responses(mock_sock, config)
            
            # Check for timeout log
            assert any("Discovery timeout reached" in record.message for record in caplog.records)
            assert any("0 server(s)" in record.message for record in caplog.records)
    
    def test_receive_socket_error_logged(self, caplog):
        """Test that socket errors during receive are logged."""
        with caplog.at_level(logging.ERROR):
            mock_sock = MagicMock()
            mock_sock.recvfrom.side_effect = OSError("Connection reset")
            
            config = ClientConfig()
            results = receive_responses(mock_sock, config)
            
            # Check for error log
            assert any("Socket error while receiving responses" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)


class TestDiscoverErrorHandling:
    """Tests for error handling in discover() function."""
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_oserror_returns_empty_list(self, mock_discover, caplog):
        """Test that OSError returns empty list and is logged."""
        with caplog.at_level(logging.ERROR):
            mock_discover.side_effect = OSError("Network unreachable")
            
            results = discover()
            
            assert len(results) == 0
            assert any("Network error during discovery" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_importerror_returns_empty_list(self, mock_discover, caplog):
        """Test that ImportError returns empty list and is logged."""
        with caplog.at_level(logging.ERROR):
            mock_discover.side_effect = ImportError("No module named 'netifaces'")
            
            results = discover()
            
            assert len(results) == 0
            assert any("Missing network interface libraries" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_unexpected_error_returns_empty_list(self, mock_discover, caplog):
        """Test that unexpected errors return empty list and are logged."""
        with caplog.at_level(logging.ERROR):
            mock_discover.side_effect = ValueError("Unexpected error")
            
            results = discover()
            
            assert len(results) == 0
            assert any("Unexpected error during discovery" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_success_logs_info(self, mock_discover, caplog):
        """Test that successful discovery is logged."""
        with caplog.at_level(logging.INFO):
            mock_discover.return_value = [
                DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response")
            ]
            
            results = discover()
            
            assert len(results) == 1
            assert any("Starting server discovery" in record.message for record in caplog.records)


class TestDiscoverOneErrorHandling:
    """Tests for error handling in discover_one() function."""
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_one_oserror_returns_none(self, mock_discover, caplog):
        """Test that discover_one returns None when discover() fails."""
        with caplog.at_level(logging.ERROR):
            mock_discover.side_effect = OSError("Network error")
            
            result = discover_one()
            
            assert result is None
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_one_success_logs_debug(self, mock_discover, caplog):
        """Test that discover_one logs debug messages."""
        with caplog.at_level(logging.DEBUG):
            mock_discover.return_value = [
                DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response")
            ]
            
            result = discover_one()
            
            assert result is not None
            assert any("discover_one() called" in record.message for record in caplog.records)
            assert any("discover_one() found server" in record.message for record in caplog.records)


class TestMultiInterfaceDiscoveryLogging:
    """Tests for logging in multi-interface discovery."""
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_multi_interface_logs_interface_selection(self, mock_receive, mock_send, mock_create, mock_select, caplog):
        """Test that interface selection is logged."""
        with caplog.at_level(logging.INFO):
            interfaces = [
                InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            ]
            mock_select.return_value = interfaces
            mock_sock = MagicMock()
            mock_create.return_value = mock_sock
            mock_receive.return_value = []
            
            config = ClientConfig()
            discover_servers_multi_interface(config)
            
            assert any("Starting multi-interface discovery" in record.message for record in caplog.records)
            assert any("Selected 1 interface(s)" in record.message for record in caplog.records)
    
    @patch('discovery_client.network.socket.select_interfaces')
    def test_no_interfaces_logs_warning(self, mock_select, caplog):
        """Test that no interfaces selected logs warning."""
        with caplog.at_level(logging.WARNING):
            mock_select.return_value = []
            
            config = ClientConfig()
            results = discover_servers_multi_interface(config)
            
            assert len(results) == 0
            assert any("No network interfaces selected" in record.message for record in caplog.records)
            assert any(record.levelname == "WARNING" for record in caplog.records)
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_interface_send_failure_logs_warning(self, mock_receive, mock_send, mock_create, mock_select, caplog):
        """Test that interface send failures are logged as warnings."""
        with caplog.at_level(logging.WARNING):
            interfaces = [
                InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            ]
            mock_select.return_value = interfaces
            mock_sock = MagicMock()
            mock_create.return_value = mock_sock
            mock_send.side_effect = OSError("Send failed")
            mock_receive.return_value = []
            
            config = ClientConfig()
            results = discover_servers_multi_interface(config)
            
            assert any("Failed to send discovery request on interface" in record.message for record in caplog.records)
            assert any(record.levelname == "WARNING" for record in caplog.records)
    
    @patch('discovery_client.network.socket.select_interfaces')
    def test_interface_selection_error_logged(self, mock_select, caplog):
        """Test that interface selection errors are logged."""
        with caplog.at_level(logging.ERROR):
            mock_select.side_effect = ImportError("No module named 'netifaces'")
            
            config = ClientConfig()
            
            with pytest.raises(ImportError):
                discover_servers_multi_interface(config)
            
            assert any("Failed to enumerate network interfaces" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)


class TestGetInterfaceBroadcastLogging:
    """Tests for logging in get_interface_broadcast."""
    
    def test_broadcast_from_interface_logged(self, caplog):
        """Test that using interface broadcast is logged."""
        with caplog.at_level(logging.DEBUG):
            iface = InterfaceInfo(
                name="eth0",
                ip="192.168.1.100",
                netmask="255.255.255.0",
                broadcast="192.168.1.255"
            )
            
            broadcast = get_interface_broadcast(iface)
            
            assert broadcast == "192.168.1.255"
            assert any("Using broadcast address from interface" in record.message for record in caplog.records)
    
    def test_computed_broadcast_logged(self, caplog):
        """Test that computed broadcast is logged."""
        with caplog.at_level(logging.DEBUG):
            iface = InterfaceInfo(
                name="eth0",
                ip="192.168.1.100",
                netmask="255.255.255.0",
                broadcast=None
            )
            
            broadcast = get_interface_broadcast(iface)
            
            assert broadcast == "192.168.1.255"
            assert any("Computed broadcast address" in record.message for record in caplog.records)
    
    def test_broadcast_computation_error_logged(self, caplog):
        """Test that broadcast computation errors are logged."""
        with caplog.at_level(logging.ERROR):
            iface = InterfaceInfo(
                name="eth0",
                ip="invalid",
                netmask="255.255.255.0",
                broadcast=None
            )
            
            with pytest.raises(ValueError):
                get_interface_broadcast(iface)
            
            assert any("Failed to compute broadcast address" in record.message for record in caplog.records)
            assert any(record.levelname == "ERROR" for record in caplog.records)


class TestErrorHandlingNoExceptions:
    """Tests that discover() and discover_one() never raise exceptions."""
    
    @patch('discovery_client.network.socket.discover_servers_multi_interface')
    def test_discover_handles_all_exceptions(self, mock_discover):
        """Test that discover() handles all exception types."""
        exception_types = [
            OSError("Network error"),
            ImportError("Missing library"),
            ValueError("Invalid value"),
            KeyError("Missing key"),
            RuntimeError("Runtime error"),
        ]
        
        for exc in exception_types:
            mock_discover.side_effect = exc
            # Should not raise, should return empty list
            results = discover()
            assert isinstance(results, list)
            assert len(results) == 0
    
    @patch('discovery_client.network.socket.discover_servers_multi_interface')
    def test_discover_one_handles_all_exceptions(self, mock_discover):
        """Test that discover_one() handles all exception types."""
        exception_types = [
            OSError("Network error"),
            ImportError("Missing library"),
            ValueError("Invalid value"),
        ]
        
        for exc in exception_types:
            mock_discover.side_effect = exc
            # Should not raise, should return None
            result = discover_one()
            assert result is None


class TestLoggingLevels:
    """Tests for appropriate log levels."""
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_info_level_logs(self, mock_receive, mock_send, mock_create, mock_select, caplog):
        """Test that important events are logged at INFO level."""
        with caplog.at_level(logging.INFO):
            interfaces = [InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255")]
            mock_select.return_value = interfaces
            mock_sock = MagicMock()
            mock_create.return_value = mock_sock
            mock_receive.return_value = []
            
            config = ClientConfig()
            discover_servers_multi_interface(config)
            
            info_records = [r for r in caplog.records if r.levelname == "INFO"]
            assert len(info_records) > 0
            assert any("Starting multi-interface discovery" in r.message for r in info_records)
    
    def test_warning_level_for_invalid_responses(self, caplog):
        """Test that invalid responses are logged at WARNING level."""
        with caplog.at_level(logging.WARNING):
            mock_sock = MagicMock()
            mock_sock.recvfrom.side_effect = [
                (b"INVALID", ("192.168.1.100", 12345)),
                socket.timeout,
            ]
            
            config = ClientConfig()
            receive_responses(mock_sock, config)
            
            warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warning_records) > 0
            assert any("Received invalid response" in r.message for r in warning_records)
    
    def test_error_level_for_socket_errors(self, caplog):
        """Test that socket errors are logged at ERROR level."""
        with caplog.at_level(logging.ERROR):
            mock_sock = MagicMock()
            mock_sock.sendto.side_effect = OSError("Permission denied")
            
            with pytest.raises(OSError):
                send_discovery_request(mock_sock, b"DISCOVER_SERVER", 9999)
            
            error_records = [r for r in caplog.records if r.levelname == "ERROR"]
            assert len(error_records) > 0
            assert any("Failed to send discovery request" in r.message for r in error_records)
