"""
Unit tests for discovery_client.network.utils module.

Tests netmask-to-prefix conversion, network range computation,
and broadcast address calculation.
"""
import pytest
import ipaddress
from discovery_client.network.utils import (
    netmask_to_prefix,
    prefix_to_netmask,
    network_from_ip_and_mask,
    broadcast_from_ip_and_mask,
)


class TestNetmaskToPrefix:
    """Tests for netmask_to_prefix function."""
    
    def test_common_masks(self):
        """Test conversion of common netmasks."""
        test_cases = [
            ("255.0.0.0", 8),      # Class A
            ("255.255.0.0", 16),   # Class B
            ("255.255.255.0", 24), # Class C
            ("255.255.255.248", 29), # /29 subnet
            ("255.255.255.252", 30), # /30 (point-to-point)
            ("255.255.255.255", 32), # Single host
            ("0.0.0.0", 0),        # Default route
        ]
        
        for netmask, expected_prefix in test_cases:
            assert netmask_to_prefix(netmask) == expected_prefix, \
                f"Failed for netmask {netmask}"
    
    def test_edge_cases(self):
        """Test edge case netmasks."""
        assert netmask_to_prefix("128.0.0.0") == 1
        assert netmask_to_prefix("192.0.0.0") == 2
        assert netmask_to_prefix("224.0.0.0") == 3
        assert netmask_to_prefix("240.0.0.0") == 4
        assert netmask_to_prefix("248.0.0.0") == 5
        assert netmask_to_prefix("252.0.0.0") == 6
        assert netmask_to_prefix("254.0.0.0") == 7
    
    def test_non_contiguous_masks(self):
        """Test that non-contiguous masks raise ValueError."""
        non_contiguous_masks = [
            "255.255.0.255",  # Has 0s in the middle
            "255.0.255.0",    # Non-contiguous pattern
            "128.128.128.128", # Non-contiguous
            "192.0.0.192",    # Non-contiguous
        ]
        
        for mask in non_contiguous_masks:
            with pytest.raises(ValueError, match="Non-contiguous"):
                netmask_to_prefix(mask)
    
    def test_invalid_formats(self):
        """Test that invalid netmask formats raise ValueError."""
        invalid_masks = [
            "256.255.255.0",  # Out of range
            "255.255.255",    # Missing octet
            "255.255.255.0.0", # Too many octets
            "not.a.mask",     # Not a valid IP
            "",               # Empty string
            "255.255.255.256", # Invalid octet value
        ]
        
        for mask in invalid_masks:
            with pytest.raises(ValueError):
                netmask_to_prefix(mask)


class TestPrefixToNetmask:
    """Tests for prefix_to_netmask function."""
    
    def test_common_prefixes(self):
        """Test conversion of common prefix lengths."""
        test_cases = [
            (8, "255.0.0.0"),
            (16, "255.255.0.0"),
            (24, "255.255.255.0"),
            (29, "255.255.255.248"),
            (30, "255.255.255.252"),
            (32, "255.255.255.255"),
            (0, "0.0.0.0"),
        ]
        
        for prefix, expected_netmask in test_cases:
            assert prefix_to_netmask(prefix) == expected_netmask, \
                f"Failed for prefix /{prefix}"
    
    def test_edge_prefixes(self):
        """Test edge case prefix lengths."""
        assert prefix_to_netmask(1) == "128.0.0.0"
        assert prefix_to_netmask(2) == "192.0.0.0"
        assert prefix_to_netmask(3) == "224.0.0.0"
        assert prefix_to_netmask(4) == "240.0.0.0"
        assert prefix_to_netmask(5) == "248.0.0.0"
        assert prefix_to_netmask(6) == "252.0.0.0"
        assert prefix_to_netmask(7) == "254.0.0.0"
        assert prefix_to_netmask(31) == "255.255.255.254"
    
    def test_invalid_prefixes(self):
        """Test that invalid prefix lengths raise ValueError."""
        invalid_prefixes = [-1, 33, 100, -10]
        
        for prefix in invalid_prefixes:
            with pytest.raises(ValueError, match="between 0 and 32"):
                prefix_to_netmask(prefix)
    
    def test_round_trip(self):
        """Test that netmask_to_prefix and prefix_to_netmask are inverse operations."""
        test_prefixes = [0, 8, 16, 24, 29, 30, 32]
        
        for prefix in test_prefixes:
            netmask = prefix_to_netmask(prefix)
            round_trip_prefix = netmask_to_prefix(netmask)
            assert round_trip_prefix == prefix, \
                f"Round trip failed for prefix /{prefix}: {netmask} -> /{round_trip_prefix}"


class TestNetworkFromIPAndMask:
    """Tests for network_from_ip_and_mask function."""
    
    def test_with_netmask_string(self):
        """Test network creation with netmask as string."""
        network = network_from_ip_and_mask("192.168.1.100", "255.255.255.0")
        assert isinstance(network, ipaddress.IPv4Network)
        assert str(network) == "192.168.1.0/24"
        assert network.network_address == ipaddress.IPv4Address("192.168.1.0")
    
    def test_with_prefix_int(self):
        """Test network creation with prefix as integer."""
        network = network_from_ip_and_mask("10.0.0.1", 8)
        assert isinstance(network, ipaddress.IPv4Network)
        assert str(network) == "10.0.0.0/8"
        assert network.network_address == ipaddress.IPv4Address("10.0.0.0")
    
    def test_with_prefix_string(self):
        """Test network creation with prefix as string (e.g., '/24')."""
        network = network_from_ip_and_mask("172.16.0.1", "/16")
        assert isinstance(network, ipaddress.IPv4Network)
        assert str(network) == "172.16.0.0/16"
    
    def test_common_networks(self):
        """Test network creation for common network sizes."""
        test_cases = [
            ("192.168.1.100", "255.255.255.0", "192.168.1.0/24"),
            ("10.0.0.1", 8, "10.0.0.0/8"),
            ("172.16.5.10", 16, "172.16.0.0/16"),
            ("192.168.1.100", 29, "192.168.1.96/29"),
        ]
        
        for ip, mask, expected_network in test_cases:
            network = network_from_ip_and_mask(ip, mask)
            assert str(network) == expected_network, \
                f"Failed for {ip}/{mask}"
    
    def test_invalid_ip(self):
        """Test that invalid IP addresses raise ValueError."""
        invalid_ips = [
            "256.1.1.1",
            "192.168.1",
            "not.an.ip",
            "",
            "192.168.1.1.1",
        ]
        
        for ip in invalid_ips:
            with pytest.raises(ValueError):
                network_from_ip_and_mask(ip, "255.255.255.0")
    
    def test_invalid_mask(self):
        """Test that invalid masks raise ValueError."""
        with pytest.raises(ValueError):
            network_from_ip_and_mask("192.168.1.1", "invalid")
        
        with pytest.raises(ValueError):
            network_from_ip_and_mask("192.168.1.1", 33)
        
        with pytest.raises(ValueError):
            network_from_ip_and_mask("192.168.1.1", -1)
    
    def test_invalid_type(self):
        """Test that invalid mask types raise TypeError."""
        with pytest.raises(TypeError):
            network_from_ip_and_mask("192.168.1.1", None)
        
        with pytest.raises(TypeError):
            network_from_ip_and_mask("192.168.1.1", [])


class TestBroadcastFromIPAndMask:
    """Tests for broadcast_from_ip_and_mask function."""
    
    def test_with_netmask_string(self):
        """Test broadcast calculation with netmask as string."""
        broadcast = broadcast_from_ip_and_mask("192.168.1.100", "255.255.255.0")
        assert broadcast == "192.168.1.255"
    
    def test_with_prefix_int(self):
        """Test broadcast calculation with prefix as integer."""
        broadcast = broadcast_from_ip_and_mask("10.0.0.1", 8)
        assert broadcast == "10.255.255.255"
    
    def test_common_broadcasts(self):
        """Test broadcast calculation for common network sizes."""
        test_cases = [
            ("192.168.1.100", "255.255.255.0", "192.168.1.255"),
            ("10.0.0.1", 8, "10.255.255.255"),
            ("172.16.5.10", 16, "172.16.255.255"),
            ("192.168.1.100", 29, "192.168.1.103"),
            ("192.168.1.100", 30, "192.168.1.103"),
            ("192.168.1.100", 32, "192.168.1.100"),  # /32 has no broadcast
        ]
        
        for ip, mask, expected_broadcast in test_cases:
            broadcast = broadcast_from_ip_and_mask(ip, mask)
            assert broadcast == expected_broadcast, \
                f"Failed for {ip}/{mask}: expected {expected_broadcast}, got {broadcast}"
    
    def test_edge_cases(self):
        """Test edge case broadcast addresses."""
        # /31 networks (point-to-point, RFC 3021)
        broadcast = broadcast_from_ip_and_mask("192.168.1.0", 31)
        assert broadcast == "192.168.1.1"
        
        # /32 network (single host)
        broadcast = broadcast_from_ip_and_mask("192.168.1.1", 32)
        assert broadcast == "192.168.1.1"
        
        # /0 network (default route)
        broadcast = broadcast_from_ip_and_mask("0.0.0.0", 0)
        assert broadcast == "255.255.255.255"
    
    def test_invalid_inputs(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            broadcast_from_ip_and_mask("256.1.1.1", "255.255.255.0")
        
        with pytest.raises(ValueError):
            broadcast_from_ip_and_mask("192.168.1.1", "255.255.0.255")  # Non-contiguous
        
        with pytest.raises(ValueError):
            broadcast_from_ip_and_mask("192.168.1.1", 33)


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_full_workflow(self):
        """Test a complete workflow using all functions."""
        ip = "192.168.1.100"
        netmask = "255.255.255.0"
        
        # Convert netmask to prefix
        prefix = netmask_to_prefix(netmask)
        assert prefix == 24
        
        # Convert prefix back to netmask
        round_trip_netmask = prefix_to_netmask(prefix)
        assert round_trip_netmask == netmask
        
        # Create network
        network = network_from_ip_and_mask(ip, netmask)
        assert str(network) == "192.168.1.0/24"
        
        # Calculate broadcast
        broadcast = broadcast_from_ip_and_mask(ip, netmask)
        assert broadcast == "192.168.1.255"
        assert broadcast == str(network.broadcast_address)
    
    def test_multiple_network_sizes(self):
        """Test functions with various network sizes."""
        test_configs = [
            ("10.0.0.1", 8, "10.0.0.0/8", "10.255.255.255"),
            ("172.16.5.10", 16, "172.16.0.0/16", "172.16.255.255"),
            ("192.168.1.100", 24, "192.168.1.0/24", "192.168.1.255"),
            ("192.168.1.100", 29, "192.168.1.96/29", "192.168.1.103"),
        ]
        
        for ip, prefix, expected_network, expected_broadcast in test_configs:
            # Test with prefix
            network = network_from_ip_and_mask(ip, prefix)
            assert str(network) == expected_network
            
            broadcast = broadcast_from_ip_and_mask(ip, prefix)
            assert broadcast == expected_broadcast
            
            # Test with netmask string
            netmask = prefix_to_netmask(prefix)
            network2 = network_from_ip_and_mask(ip, netmask)
            assert str(network2) == expected_network
            
            broadcast2 = broadcast_from_ip_and_mask(ip, netmask)
            assert broadcast2 == expected_broadcast
