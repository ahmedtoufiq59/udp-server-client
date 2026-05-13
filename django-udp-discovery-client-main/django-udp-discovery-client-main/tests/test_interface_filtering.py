"""
Tests for interface filtering and selection functionality.

Tests the select_interfaces function with various whitelist/blacklist combinations.
"""
import pytest
from unittest.mock import patch, MagicMock
from discovery_client import ClientConfig
from discovery_client.network.interfaces import select_interfaces, InterfaceInfo


# Mock interface data for testing
MOCK_INTERFACES = [
    InterfaceInfo(name="eth0", ip="192.168.1.100", netmask="255.255.255.0", broadcast="192.168.1.255"),
    InterfaceInfo(name="eth1", ip="10.0.0.5", netmask="255.0.0.0", broadcast="10.255.255.255"),
    InterfaceInfo(name="wlan0", ip="172.16.0.1", netmask="255.255.0.0", broadcast="172.16.255.255"),
    InterfaceInfo(name="docker0", ip="172.17.0.1", netmask="255.255.0.0", broadcast="172.17.255.255"),
    InterfaceInfo(name="veth123", ip="192.168.2.1", netmask="255.255.255.0", broadcast="192.168.2.255"),
]


class TestSelectInterfacesNoFiltering:
    """Test select_interfaces with no whitelist/blacklist."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_no_whitelist_no_blacklist(self, mock_get_interfaces):
        """Test that all interfaces are returned when no filters are set."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(
            interfaces_whitelist=None,
            interfaces_blacklist=None
        )
        
        result = select_interfaces(config)
        
        assert len(result) == len(MOCK_INTERFACES)
        assert result == MOCK_INTERFACES
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_empty_whitelist_empty_blacklist(self, mock_get_interfaces):
        """Test that empty lists are treated as None (no filtering)."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # Note: ClientConfig doesn't allow empty lists, but test the behavior
        # when both are effectively None
        config = ClientConfig()
        # interfaces_whitelist and interfaces_blacklist default to None
        
        result = select_interfaces(config)
        
        assert len(result) == len(MOCK_INTERFACES)
        assert result == MOCK_INTERFACES


class TestSelectInterfacesWhitelist:
    """Test select_interfaces with whitelist only."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_single_interface(self, mock_get_interfaces):
        """Test whitelist with a single interface."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_whitelist=["eth0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 1
        assert result[0].name == "eth0"
        assert result[0].ip == "192.168.1.100"
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_multiple_interfaces(self, mock_get_interfaces):
        """Test whitelist with multiple interfaces."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_whitelist=["eth0", "wlan0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 2
        names = {iface.name for iface in result}
        assert names == {"eth0", "wlan0"}
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_nonexistent_interface(self, mock_get_interfaces):
        """Test whitelist with interface that doesn't exist."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_whitelist=["nonexistent"])
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_case_sensitive(self, mock_get_interfaces):
        """Test that whitelist matching is case-sensitive."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # "Eth0" should not match "eth0"
        config = ClientConfig(interfaces_whitelist=["Eth0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_partial_match(self, mock_get_interfaces):
        """Test that whitelist requires exact match (not partial)."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # "eth" should not match "eth0"
        config = ClientConfig(interfaces_whitelist=["eth"])
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []


class TestSelectInterfacesBlacklist:
    """Test select_interfaces with blacklist only."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_blacklist_single_interface(self, mock_get_interfaces):
        """Test blacklist with a single interface."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_blacklist=["docker0"])
        
        result = select_interfaces(config)
        
        assert len(result) == len(MOCK_INTERFACES) - 1
        names = {iface.name for iface in result}
        assert "docker0" not in names
        assert "eth0" in names
        assert "eth1" in names
        assert "wlan0" in names
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_blacklist_multiple_interfaces(self, mock_get_interfaces):
        """Test blacklist with multiple interfaces."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_blacklist=["docker0", "veth123"])
        
        result = select_interfaces(config)
        
        assert len(result) == len(MOCK_INTERFACES) - 2
        names = {iface.name for iface in result}
        assert "docker0" not in names
        assert "veth123" not in names
        assert "eth0" in names
        assert "eth1" in names
        assert "wlan0" in names
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_blacklist_nonexistent_interface(self, mock_get_interfaces):
        """Test blacklist with interface that doesn't exist."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_blacklist=["nonexistent"])
        
        result = select_interfaces(config)
        
        # Should return all interfaces (none were blacklisted)
        assert len(result) == len(MOCK_INTERFACES)
        assert result == MOCK_INTERFACES
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_blacklist_case_sensitive(self, mock_get_interfaces):
        """Test that blacklist matching is case-sensitive."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # "Docker0" should not match "docker0"
        config = ClientConfig(interfaces_blacklist=["Docker0"])
        
        result = select_interfaces(config)
        
        # Should return all interfaces (case mismatch, nothing blacklisted)
        assert len(result) == len(MOCK_INTERFACES)
        names = {iface.name for iface in result}
        assert "docker0" in names  # Not blacklisted due to case mismatch


class TestSelectInterfacesBothFilters:
    """Test select_interfaces with both whitelist and blacklist."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_then_blacklist(self, mock_get_interfaces):
        """Test that whitelist is applied first, then blacklist."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # Whitelist: eth0, eth1, wlan0
        # Blacklist: eth1
        # Expected: eth0, wlan0 (eth1 is blacklisted even though whitelisted)
        config = ClientConfig(
            interfaces_whitelist=["eth0", "eth1", "wlan0"],
            interfaces_blacklist=["eth1"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 2
        names = {iface.name for iface in result}
        assert names == {"eth0", "wlan0"}
        assert "eth1" not in names  # Blacklisted
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_then_blacklist_no_overlap(self, mock_get_interfaces):
        """Test whitelist and blacklist with no overlapping interfaces."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # Whitelist: eth0, wlan0
        # Blacklist: docker0 (not in whitelist, so doesn't matter)
        config = ClientConfig(
            interfaces_whitelist=["eth0", "wlan0"],
            interfaces_blacklist=["docker0"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 2
        names = {iface.name for iface in result}
        assert names == {"eth0", "wlan0"}
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_then_blacklist_all_blacklisted(self, mock_get_interfaces):
        """Test when all whitelisted interfaces are also blacklisted."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # Whitelist: eth0, eth1
        # Blacklist: eth0, eth1
        config = ClientConfig(
            interfaces_whitelist=["eth0", "eth1"],
            interfaces_blacklist=["eth0", "eth1"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_then_blacklist_empty_result(self, mock_get_interfaces):
        """Test when whitelist results in empty set, then blacklist."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        # Whitelist: nonexistent interface
        # Blacklist: anything (shouldn't matter since whitelist is empty)
        config = ClientConfig(
            interfaces_whitelist=["nonexistent"],
            interfaces_blacklist=["eth0"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []


class TestSelectInterfacesEdgeCases:
    """Test edge cases for select_interfaces."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_empty_interface_list(self, mock_get_interfaces):
        """Test with no available interfaces."""
        mock_get_interfaces.return_value = []
        
        config = ClientConfig(
            interfaces_whitelist=["eth0"],
            interfaces_blacklist=["docker0"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_single_interface_whitelisted(self, mock_get_interfaces):
        """Test with single interface that matches whitelist."""
        single_interface = [MOCK_INTERFACES[0]]  # eth0
        mock_get_interfaces.return_value = single_interface
        
        config = ClientConfig(interfaces_whitelist=["eth0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 1
        assert result[0].name == "eth0"
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_single_interface_blacklisted(self, mock_get_interfaces):
        """Test with single interface that is blacklisted."""
        single_interface = [MOCK_INTERFACES[0]]  # eth0
        mock_get_interfaces.return_value = single_interface
        
        config = ClientConfig(interfaces_blacklist=["eth0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_whitelist_all_available(self, mock_get_interfaces):
        """Test whitelist that includes all available interfaces."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        all_names = [iface.name for iface in MOCK_INTERFACES]
        config = ClientConfig(interfaces_whitelist=all_names)
        
        result = select_interfaces(config)
        
        assert len(result) == len(MOCK_INTERFACES)
        assert set(iface.name for iface in result) == set(all_names)
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_blacklist_all_available(self, mock_get_interfaces):
        """Test blacklist that excludes all available interfaces."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        all_names = [iface.name for iface in MOCK_INTERFACES]
        config = ClientConfig(interfaces_blacklist=all_names)
        
        result = select_interfaces(config)
        
        assert len(result) == 0
        assert result == []


class TestSelectInterfacesIntegration:
    """Integration tests for select_interfaces with real ClientConfig."""
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_with_load_config(self, mock_get_interfaces):
        """Test select_interfaces with config from load_config."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        from discovery_client import load_config
        
        config = load_config(
            interfaces_whitelist=["eth0", "wlan0"],
            interfaces_blacklist=["docker0"]
        )
        
        result = select_interfaces(config)
        
        assert len(result) == 2
        names = {iface.name for iface in result}
        assert names == {"eth0", "wlan0"}
    
    @patch('discovery_client.network.interfaces.get_interfaces')
    def test_preserves_interface_data(self, mock_get_interfaces):
        """Test that filtering preserves all interface data."""
        mock_get_interfaces.return_value = MOCK_INTERFACES
        
        config = ClientConfig(interfaces_whitelist=["eth0"])
        
        result = select_interfaces(config)
        
        assert len(result) == 1
        filtered_iface = result[0]
        original_iface = MOCK_INTERFACES[0]
        
        # All attributes should be preserved
        assert filtered_iface.name == original_iface.name
        assert filtered_iface.ip == original_iface.ip
        assert filtered_iface.netmask == original_iface.netmask
        assert filtered_iface.broadcast == original_iface.broadcast
