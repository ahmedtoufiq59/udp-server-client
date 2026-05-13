"""
Tests for discovery API and DiscoveryResult model.

Tests the API definitions and data structures without requiring network implementation.
"""
import pytest
from discovery_client import (
    DiscoveryResult,
    discover,
    discover_one,
    ClientConfig,
    load_config,
)
from typing import List, Optional
from unittest.mock import patch


class TestImports:
    """Test that all discovery API components are importable."""
    
    def test_import_discovery_result(self):
        """Test that DiscoveryResult can be imported."""
        from discovery_client import DiscoveryResult
        assert DiscoveryResult is not None
    
    def test_import_discover(self):
        """Test that discover function can be imported."""
        from discovery_client import discover
        assert callable(discover)
    
    def test_import_discover_one(self):
        """Test that discover_one function can be imported."""
        from discovery_client import discover_one
        assert callable(discover_one)
    
    def test_import_all_together(self):
        """Test importing all discovery API components together."""
        from discovery_client import DiscoveryResult, discover, discover_one
        assert DiscoveryResult is not None
        assert callable(discover)
        assert callable(discover_one)
    
    def test_import_from_main_module(self):
        """Test that imports work from main discovery_client module."""
        import discovery_client
        assert hasattr(discovery_client, 'DiscoveryResult')
        assert hasattr(discovery_client, 'discover')
        assert hasattr(discovery_client, 'discover_one')
        assert hasattr(discovery_client, 'ClientConfig')
        assert hasattr(discovery_client, 'load_config')


class TestDiscoveryResult:
    """Test DiscoveryResult dataclass instantiation and attributes."""
    
    def test_create_with_required_fields(self):
        """Test creating DiscoveryResult with required fields only."""
        result = DiscoveryResult(
            ip="192.168.1.100",
            port=8000,
            raw_response=b"SERVER_IP:192.168.1.100:8000"
        )
        
        assert result.ip == "192.168.1.100"
        assert result.port == 8000
        assert result.raw_response == b"SERVER_IP:192.168.1.100:8000"
        assert result.extra is None
    
    def test_create_with_extra_field(self):
        """Test creating DiscoveryResult with extra metadata."""
        extra_data = {"hostname": "server1", "version": "1.0.0"}
        result = DiscoveryResult(
            ip="10.0.0.5",
            port=9000,
            raw_response=b"SERVER_IP:10.0.0.5:9000",
            extra=extra_data
        )
        
        assert result.ip == "10.0.0.5"
        assert result.port == 9000
        assert result.raw_response == b"SERVER_IP:10.0.0.5:9000"
        assert result.extra == extra_data
        assert result.extra["hostname"] == "server1"
    
    def test_validate_ip_string(self):
        """Test that IP must be a non-empty string."""
        # Valid IP
        result = DiscoveryResult(
            ip="192.168.1.1",
            port=8000,
            raw_response=b"SERVER_IP:192.168.1.1:8000"
        )
        assert result.ip == "192.168.1.1"
        
        # Invalid: empty string
        with pytest.raises(ValueError, match="ip must be a non-empty string"):
            DiscoveryResult(ip="", port=8000, raw_response=b"test")
        
        # Invalid: not a string
        with pytest.raises(ValueError, match="ip must be a non-empty string"):
            DiscoveryResult(ip=123, port=8000, raw_response=b"test")
    
    def test_validate_port_range(self):
        """Test that port must be in valid range 1-65535."""
        # Valid ports
        for port in [1, 80, 8000, 65535]:
            result = DiscoveryResult(
                ip="192.168.1.1",
                port=port,
                raw_response=b"test"
            )
            assert result.port == port
        
        # Invalid: too low
        with pytest.raises(ValueError, match="port must be an integer between 1 and 65535"):
            DiscoveryResult(ip="192.168.1.1", port=0, raw_response=b"test")
        
        # Invalid: too high
        with pytest.raises(ValueError, match="port must be an integer between 1 and 65535"):
            DiscoveryResult(ip="192.168.1.1", port=65536, raw_response=b"test")
        
        # Invalid: not an integer
        with pytest.raises(ValueError, match="port must be an integer between 1 and 65535"):
            DiscoveryResult(ip="192.168.1.1", port="8000", raw_response=b"test")
    
    def test_validate_raw_response_bytes(self):
        """Test that raw_response must be bytes."""
        # Valid: bytes
        result = DiscoveryResult(
            ip="192.168.1.1",
            port=8000,
            raw_response=b"SERVER_IP:192.168.1.1:8000"
        )
        assert isinstance(result.raw_response, bytes)
        
        # Invalid: string
        with pytest.raises(ValueError, match="raw_response must be bytes"):
            DiscoveryResult(
                ip="192.168.1.1",
                port=8000,
                raw_response="SERVER_IP:192.168.1.1:8000"
            )
        
        # Invalid: None
        with pytest.raises(ValueError, match="raw_response must be bytes"):
            DiscoveryResult(ip="192.168.1.1", port=8000, raw_response=None)
    
    def test_validate_extra_dict(self):
        """Test that extra must be a dict or None."""
        # Valid: None
        result = DiscoveryResult(
            ip="192.168.1.1",
            port=8000,
            raw_response=b"test",
            extra=None
        )
        assert result.extra is None
        
        # Valid: dict
        result = DiscoveryResult(
            ip="192.168.1.1",
            port=8000,
            raw_response=b"test",
            extra={"key": "value"}
        )
        assert isinstance(result.extra, dict)
        
        # Invalid: not a dict
        with pytest.raises(ValueError, match="extra must be a dict or None"):
            DiscoveryResult(
                ip="192.168.1.1",
                port=8000,
                raw_response=b"test",
                extra="not a dict"
            )
    
    def test_result_repr(self):
        """Test that DiscoveryResult has a useful string representation."""
        result = DiscoveryResult(
            ip="192.168.1.100",
            port=8000,
            raw_response=b"SERVER_IP:192.168.1.100:8000"
        )
        # Dataclass should have __repr__
        repr_str = repr(result)
        assert "DiscoveryResult" in repr_str
        assert "192.168.1.100" in repr_str
        assert "8000" in repr_str


class TestDiscoverFunction:
    """Test discover() function API definition."""
    
    def test_discover_signature(self):
        """Test that discover() has the correct signature."""
        import inspect
        sig = inspect.signature(discover)
        
        # Should accept optional config parameter
        params = list(sig.parameters.keys())
        assert 'config' in params
        
        # Check parameter annotation
        param = sig.parameters['config']
        assert param.annotation == Optional[ClientConfig] or param.annotation == 'Optional[ClientConfig]'
        assert param.default is None
    
    def test_discover_return_type_annotation(self):
        """Test that discover() has correct return type annotation."""
        import inspect
        sig = inspect.signature(discover)
        return_annotation = sig.return_annotation
        
        # Should return List[DiscoveryResult]
        assert 'List' in str(return_annotation) or 'list' in str(return_annotation).lower()
        assert 'DiscoveryResult' in str(return_annotation)
    
    @patch("discovery_client.discover_servers_multi_interface")
    def test_discover_calls_multi_interface_and_returns_list(self, mock_discover):
        """Test that discover() calls the multi-interface implementation and returns its results."""
        mock_discover.return_value = []
        results = discover()
        assert isinstance(results, list)
        mock_discover.assert_called_once()
    
    def test_discover_docstring(self):
        """Test that discover() has documentation."""
        assert discover.__doc__ is not None
        assert len(discover.__doc__.strip()) > 0
        # Should mention the protocol
        assert "DISCOVER_SERVER" in discover.__doc__ or "discovery" in discover.__doc__.lower()


class TestDiscoverOneFunction:
    """Test discover_one() function API definition."""
    
    def test_discover_one_signature(self):
        """Test that discover_one() has the correct signature."""
        import inspect
        sig = inspect.signature(discover_one)
        
        # Should accept optional config parameter
        params = list(sig.parameters.keys())
        assert 'config' in params
        
        # Check parameter annotation
        param = sig.parameters['config']
        assert param.annotation == Optional[ClientConfig] or param.annotation == 'Optional[ClientConfig]'
        assert param.default is None
    
    def test_discover_one_return_type_annotation(self):
        """Test that discover_one() has correct return type annotation."""
        import inspect
        sig = inspect.signature(discover_one)
        return_annotation = sig.return_annotation
        
        # Should return Optional[DiscoveryResult]
        # Python versions may represent this as Optional[T] or T | None
        assert (
            'Optional' in str(return_annotation)
            or 'optional' in str(return_annotation).lower()
            or 'None' in str(return_annotation)
        )
        assert 'DiscoveryResult' in str(return_annotation)
    
    @patch("discovery_client.discover_servers_multi_interface")
    def test_discover_one_returns_none_when_no_servers(self, mock_discover):
        """Test that discover_one() returns None when no servers are found."""
        mock_discover.return_value = []
        assert discover_one() is None
    
    def test_discover_one_docstring(self):
        """Test that discover_one() has documentation."""
        assert discover_one.__doc__ is not None
        assert len(discover_one.__doc__.strip()) > 0


class TestAPIIntegration:
    """Integration tests for the discovery API."""
    
    def test_api_completeness(self):
        """Test that all required API components are available."""
        # All should be importable
        from discovery_client import (
            DiscoveryResult,
            discover,
            discover_one,
            ClientConfig,
            load_config,
        )
        
        # All should be in __all__
        import discovery_client
        assert 'DiscoveryResult' in discovery_client.__all__
        assert 'discover' in discovery_client.__all__
        assert 'discover_one' in discovery_client.__all__
        assert 'ClientConfig' in discovery_client.__all__
        assert 'load_config' in discovery_client.__all__
    
    def test_result_usage_example(self):
        """Test a realistic usage example with DiscoveryResult."""
        # Create a result as if it came from discovery
        result = DiscoveryResult(
            ip="192.168.1.100",
            port=8000,
            raw_response=b"SERVER_IP:192.168.1.100:8000",
            extra={"discovered_at": "2024-01-01T00:00:00Z"}
        )
        
        # Access all fields
        assert result.ip == "192.168.1.100"
        assert result.port == 8000
        assert result.raw_response == b"SERVER_IP:192.168.1.100:8000"
        assert result.extra["discovered_at"] == "2024-01-01T00:00:00Z"
        
        # Use in a typical way
        server_url = f"http://{result.ip}:{result.port}"
        assert server_url == "http://192.168.1.100:8000"
