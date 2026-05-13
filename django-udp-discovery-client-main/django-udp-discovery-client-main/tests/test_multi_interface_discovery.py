"""
Tests for multi-interface broadcast discovery functionality.

Tests the discover_servers_multi_interface function with multiple interfaces
and deduplication.
"""
import pytest
import socket
from unittest.mock import Mock, patch, MagicMock
from discovery_client import ClientConfig
from discovery_client.network.socket import (
    discover_servers_multi_interface,
    get_interface_broadcast,
    deduplicate_results,
    create_discovery_socket,
    send_discovery_request,
    receive_responses,
)
from discovery_client.network.interfaces import InterfaceInfo
from discovery_client.results import DiscoveryResult


class TestGetInterfaceBroadcast:
    """Tests for get_interface_broadcast function."""
    
    def test_with_broadcast_address(self):
        """Test with interface that has broadcast address."""
        iface = InterfaceInfo(
            name="eth0",
            ip="192.168.1.100",
            netmask="255.255.255.0",
            broadcast="192.168.1.255"
        )
        
        broadcast = get_interface_broadcast(iface)
        
        assert broadcast == "192.168.1.255"
    
    def test_without_broadcast_address(self):
        """Test with interface that lacks broadcast address (computed)."""
        iface = InterfaceInfo(
            name="eth0",
            ip="192.168.1.100",
            netmask="255.255.255.0",
            broadcast=None
        )
        
        broadcast = get_interface_broadcast(iface)
        
        assert broadcast == "192.168.1.255"  # Computed from IP and netmask
    
    def test_computed_broadcast_different_network(self):
        """Test computed broadcast for different network."""
        iface = InterfaceInfo(
            name="eth1",
            ip="10.0.0.5",
            netmask="255.0.0.0",
            broadcast=None
        )
        
        broadcast = get_interface_broadcast(iface)
        
        assert broadcast == "10.255.255.255"


class TestDeduplicateResults:
    """Tests for deduplicate_results function."""
    
    def test_no_duplicates(self):
        """Test with no duplicate results."""
        results = [
            DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response1"),
            DiscoveryResult(ip="10.0.0.5", port=9000, raw_response=b"response2"),
        ]
        
        unique = deduplicate_results(results)
        
        assert len(unique) == 2
        assert unique == results
    
    def test_with_duplicates_same_ip_port(self):
        """Test deduplication of results with same ip:port."""
        results = [
            DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response1"),
            DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response2"),
            DiscoveryResult(ip="10.0.0.5", port=9000, raw_response=b"response3"),
        ]
        
        unique = deduplicate_results(results)
        
        assert len(unique) == 2
        assert unique[0].ip == "192.168.1.100"
        assert unique[0].port == 8000
        assert unique[0].raw_response == b"response1"  # First occurrence kept
        assert unique[1].ip == "10.0.0.5"
    
    def test_with_duplicates_different_ports(self):
        """Test that different ports are not considered duplicates."""
        results = [
            DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response1"),
            DiscoveryResult(ip="192.168.1.100", port=9000, raw_response=b"response2"),
        ]
        
        unique = deduplicate_results(results)
        
        assert len(unique) == 2  # Different ports, not duplicates
    
    def test_empty_list(self):
        """Test with empty list."""
        unique = deduplicate_results([])
        assert len(unique) == 0


class TestDiscoverServersMultiInterface:
    """Tests for discover_servers_multi_interface function."""
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_multiple_interfaces_sends_to_each(self, mock_receive, mock_send, mock_create, mock_select):
        """Test that discovery sends to each interface's broadcast address."""
        # Setup mock interfaces
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            InterfaceInfo(name="eth1", ip="10.0.0.5", netmask="255.0.0.0", broadcast="10.255.255.255"),
        ]
        mock_select.return_value = interfaces
        
        # Setup socket mock
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        mock_receive.return_value = []
        
        config = ClientConfig(
            discovery_message=b"DISCOVER_SERVER",
            discovery_port=9999,
            timeout=5.0
        )
        
        # Execute
        results = discover_servers_multi_interface(config)
        
        # Verify select_interfaces was called
        mock_select.assert_called_once_with(config)
        
        # Verify sendto was called for each interface
        assert mock_send.call_count == 2
        
        # Verify sendto was called with correct broadcast addresses
        calls = mock_send.call_args_list
        broadcast_addrs = {call[0][3] for call in calls}  # Extract broadcast addresses
        assert "192.168.1.255" in broadcast_addrs
        assert "10.255.255.255" in broadcast_addrs
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_interface_without_broadcast_computed(self, mock_receive, mock_send, mock_create, mock_select):
        """Test that broadcast is computed for interfaces without broadcast address."""
        # Interface without broadcast address
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast=None),
        ]
        mock_select.return_value = interfaces
        
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        mock_receive.return_value = []
        
        config = ClientConfig()
        
        results = discover_servers_multi_interface(config)
        
        # Verify sendto was called with computed broadcast
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        broadcast_addr = call_args[0][3]  # broadcast_address parameter
        assert broadcast_addr == "192.168.1.255"  # Computed from IP and netmask
    
    @patch('discovery_client.network.socket.select_interfaces')
    def test_no_interfaces_returns_empty(self, mock_select):
        """Test that empty interface list returns empty results."""
        mock_select.return_value = []
        
        config = ClientConfig()
        results = discover_servers_multi_interface(config)
        
        assert len(results) == 0
        mock_select.assert_called_once_with(config)
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_deduplication_of_results(self, mock_receive, mock_send, mock_create, mock_select):
        """Test that duplicate results are deduplicated."""
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            InterfaceInfo(name="eth1", ip="10.0.0.5", netmask="255.0.0.0", broadcast="10.255.255.255"),
        ]
        mock_select.return_value = interfaces
        
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        
        # Simulate same server responding from different interfaces
        duplicate_results = [
            DiscoveryResult(
                ip="192.168.1.200",
                port=8000,
                raw_response=b"SERVER_IP:192.168.1.200:8000",
                extra={"source_address": "192.168.1.255"}
            ),
            DiscoveryResult(
                ip="192.168.1.200",
                port=8000,
                raw_response=b"SERVER_IP:192.168.1.200:8000",
                extra={"source_address": "10.255.255.255"}
            ),
            DiscoveryResult(
                ip="10.0.0.10",
                port=9000,
                raw_response=b"SERVER_IP:10.0.0.10:9000"
            ),
        ]
        mock_receive.return_value = duplicate_results
        
        config = ClientConfig()
        results = discover_servers_multi_interface(config)
        
        # Should have only 2 unique results (duplicate removed)
        assert len(results) == 2
        
        # Verify unique results
        ips_ports = {(r.ip, r.port) for r in results}
        assert ("192.168.1.200", 8000) in ips_ports
        assert ("10.0.0.10", 9000) in ips_ports
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_interface_send_failure_continues(self, mock_receive, mock_send, mock_create, mock_select):
        """Test that failure to send to one interface doesn't stop others."""
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            InterfaceInfo(name="eth1", ip="10.0.0.5", netmask="255.0.0.0", broadcast="10.255.255.255"),
        ]
        mock_select.return_value = interfaces
        
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        
        # First send succeeds, second fails
        mock_send.side_effect = [None, OSError("Send failed")]
        mock_receive.return_value = []
        
        config = ClientConfig()
        results = discover_servers_multi_interface(config)
        
        # Should still attempt both sends
        assert mock_send.call_count == 2
        # Should return empty list (no responses)
        assert len(results) == 0
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_multiple_servers_multiple_interfaces(self, mock_receive, mock_send, mock_create, mock_select):
        """Test discovery with multiple servers on multiple interfaces."""
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            InterfaceInfo(name="wlan0", ip="172.16.0.1", netmask="255.255.0.0", broadcast="172.16.255.255"),
        ]
        mock_select.return_value = interfaces
        
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        
        # Multiple servers responding
        mock_receive.return_value = [
            DiscoveryResult(ip="192.168.1.200", port=8000, raw_response=b"SERVER_IP:192.168.1.200:8000"),
            DiscoveryResult(ip="192.168.1.201", port=8000, raw_response=b"SERVER_IP:192.168.1.201:8000"),
            DiscoveryResult(ip="172.16.0.10", port=9000, raw_response=b"SERVER_IP:172.16.0.10:9000"),
        ]
        
        config = ClientConfig()
        results = discover_servers_multi_interface(config)
        
        # Should have all 3 unique servers
        assert len(results) == 3
        
        # Verify sendto was called for both interfaces
        assert mock_send.call_count == 2
        
        # Verify all servers are present
        ips = {r.ip for r in results}
        assert "192.168.1.200" in ips
        assert "192.168.1.201" in ips
        assert "172.16.0.10" in ips


class TestDiscoverFunctionMultiInterface:
    """Tests for discover() function using multi-interface discovery."""
    
    @patch('discovery_client.discover_servers_multi_interface')
    def test_discover_uses_multi_interface(self, mock_discover):
        """Test that discover() uses multi-interface discovery."""
        mock_discover.return_value = []
        
        from discovery_client import discover
        
        results = discover()
        
        mock_discover.assert_called_once()
        assert len(results) == 0
    
    @patch('discovery_client.network.socket.select_interfaces')
    @patch('discovery_client.network.socket.create_discovery_socket')
    @patch('discovery_client.network.socket.send_discovery_request')
    @patch('discovery_client.network.socket.receive_responses')
    def test_discover_with_interface_filtering(self, mock_receive, mock_send, mock_create, mock_select):
        """Test discover() with interface whitelist/blacklist."""
        interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
        ]
        mock_select.return_value = interfaces
        
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock
        mock_receive.return_value = []
        
        from discovery_client import discover
        
        config = ClientConfig(interfaces_whitelist=["eth0"])
        results = discover(config=config)
        
        # Verify select_interfaces was called with config
        mock_select.assert_called_once_with(config)
        
        # Verify sendto was called
        mock_send.assert_called_once()


class TestIntegrationMultiInterface:
    """Integration tests for multi-interface discovery."""
    
    @patch('discovery_client.network.socket.socket.socket')
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_end_to_end_multi_interface(self, mock_get_interfaces, mock_socket_class):
        """Test end-to-end multi-interface discovery."""
        # Setup mock interfaces
        mock_interfaces = [
            InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
            InterfaceInfo(name="eth1", ip="10.0.0.5", netmask="255.0.0.0", broadcast=None),  # No broadcast
        ]
        mock_get_interfaces.return_value = mock_interfaces
        
        # Setup mock socket
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        
        # Mock recvfrom to return responses then timeout
        mock_sock.recvfrom.side_effect = [
            (b"SERVER_IP:192.168.1.200:8000", ("192.168.1.200", 12345)),
            (b"SERVER_IP:10.0.0.10:9000", ("10.0.0.10", 12346)),
            socket.timeout,
        ]
        
        from discovery_client import discover
        
        config = ClientConfig(timeout=5.0)
        results = discover(config=config)
        
        # Verify socket was configured
        mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        mock_sock.settimeout.assert_called_once_with(5.0)
        
        # Verify sendto was called for each interface
        sendto_calls = mock_sock.sendto.call_args_list
        assert len(sendto_calls) == 2
        
        # Verify broadcast addresses used
        broadcast_addrs = {call[0][1][0] for call in sendto_calls}  # Extract broadcast addresses
        assert "192.168.1.255" in broadcast_addrs
        assert "10.255.255.255" in broadcast_addrs  # Computed broadcast
        
        # Verify results
        assert len(results) == 2
        ips = {r.ip for r in results}
        assert "192.168.1.200" in ips
        assert "10.0.0.10" in ips
        
        # Verify deduplication (if same server responded twice, only one result)
        unique_keys = {(r.ip, r.port) for r in results}
        assert len(unique_keys) == 2  # Both unique
