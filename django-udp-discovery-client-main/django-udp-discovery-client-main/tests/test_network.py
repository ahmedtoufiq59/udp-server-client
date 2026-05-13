"""
Tests for discovery behavior when network interfaces are missing or unavailable.

Ensures the library returns [] instead of crashing when no interfaces exist
or when the network stack (netifaces/ifaddr) is unavailable.
"""
import importlib.util
import sys
from pathlib import Path

import pytest
from discovery_client import discover
from discovery_client.config import ClientConfig


class TestSegmentedNetworkDiagnosticOnce:
    """Segmented network warning must appear exactly once in sanity_check output."""

    def test_sanity_check_segmented_detected_appears_exactly_once(self, monkeypatch, capsys):
        """Run sanity_check with no servers and segmented interface; 'Segmented Network Detected' once."""
        from discovery_client.network.interfaces import InterfaceInfo

        # One corporate /16 interface so detect_segmented_network returns info
        iface = InterfaceInfo(
            name="eth0",
            ip="10.0.0.1",
            netmask="255.255.0.0",
            broadcast="10.255.255.255",
        )
        monkeypatch.setattr(
            "discovery_client.discover",
            lambda config=None: [],
        )
        monkeypatch.setattr(
            "discovery_client.network.interfaces.get_interfaces",
            lambda: [iface],
        )
        monkeypatch.setattr(
            "discovery_client.network.interfaces.select_interfaces",
            lambda config: [iface],
        )

        repo_root = Path(__file__).resolve().parent.parent
        script_path = repo_root / "scripts" / "sanity_check.py"
        spec = importlib.util.spec_from_file_location("sanity_check", script_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["sanity_check"] = mod
        try:
            spec.loader.exec_module(mod)
            mod.main()
        finally:
            sys.modules.pop("sanity_check", None)

        out = capsys.readouterr().out
        count = out.count("Segmented Network Detected")
        assert count == 1, f"Expected 'Segmented Network Detected' exactly once, got {count}. Output (excerpt): {out[:500]!r}"


class TestDiscoverNoInterfaces:
    """discover() must return empty list when no interfaces are available."""

    def test_discover_returns_empty_list_when_no_interfaces(self, monkeypatch):
        """When get_interfaces returns [], discover() returns [] and does not raise."""
        from discovery_client.network import interfaces as iface_mod
        monkeypatch.setattr(iface_mod, "get_interfaces", lambda: [])
        config = ClientConfig(timeout=0.5)
        result = discover(config=config)
        assert result == []

    def test_discover_returns_empty_list_when_import_error(self, monkeypatch):
        """When get_interfaces raises ImportError, discover() returns [] and does not raise."""

        def raise_import_error():
            raise ImportError("No netifaces or ifaddr")

        from discovery_client.network import interfaces as iface_mod
        monkeypatch.setattr(iface_mod, "get_interfaces", raise_import_error)
        config = ClientConfig(timeout=0.5)
        result = discover(config=config)
        assert result == []
