#!/usr/bin/env python3
"""
Test script to demonstrate what currently works in django-udp-discovery-client.

This script tests the implemented features:
1. Configuration system
2. Network interface enumeration

It also demonstrates that discover() function does not exist.
"""

def test_config():
    """Test the configuration system."""
    print("=" * 60)
    print("TEST 1: Configuration System")
    print("=" * 60)
    
    try:
        from discovery_client import ClientConfig, load_config
        
        # Test default config
        print("\n1.1 Default Configuration:")
        config = ClientConfig()
        print(f"   Port: {config.discovery_port}")
        print(f"   Message: {config.discovery_message}")
        print(f"   Response Prefix: {config.response_prefix}")
        print(f"   Timeout: {config.timeout}")
        print(f"   Retries: {config.retries}")
        
        # Test runtime override
        print("\n1.2 Runtime Override:")
        config2 = load_config(timeout=10.0, discovery_port=8888)
        print(f"   Port: {config2.discovery_port}")
        print(f"   Timeout: {config2.timeout}")
        
        # Test validation
        print("\n1.3 Validation Test:")
        try:
            invalid = ClientConfig(discovery_port=99999)  # Invalid port
            print("   ERROR: Validation should have failed!")
        except ValueError as e:
            print(f"   ✓ Validation works: {e}")
        
        print("\n✓ Configuration system works correctly\n")
        return True
    except Exception as e:
        print(f"\n✗ Configuration test failed: {e}\n")
        return False


def test_interfaces():
    """Test network interface enumeration."""
    print("=" * 60)
    print("TEST 2: Network Interface Enumeration")
    print("=" * 60)
    
    try:
        from discovery_client.network.interfaces import get_interfaces
        
        print("\n2.1 Getting Network Interfaces:")
        interfaces = get_interfaces()
        
        if not interfaces:
            print("   ⚠ No network interfaces found (may be normal in some environments)")
        else:
            print(f"   Found {len(interfaces)} interface(s):")
            for i, iface in enumerate(interfaces, 1):
                print(f"   {i}. {iface.name}")
                print(f"      IP: {iface.ip}")
                print(f"      Netmask: {iface.netmask}")
                print(f"      Broadcast: {iface.broadcast}")
        
        print("\n✓ Interface enumeration works correctly\n")
        return True
    except ImportError as e:
        print(f"\n✗ Missing dependency: {e}")
        print("   Install with: pip install netifaces (or ifaddr)\n")
        return False
    except Exception as e:
        print(f"\n✗ Interface enumeration failed: {e}\n")
        return False


def test_discover_function():
    """Test if discover() function exists."""
    print("=" * 60)
    print("TEST 3: Discover Function (Expected to FAIL)")
    print("=" * 60)
    
    try:
        from discovery_client import discover
        print("\n✗ ERROR: discover() function exists (unexpected!)")
        print("   Attempting to call it...")
        result = discover()
        print(f"   Result: {result}")
        return False
    except ImportError as e:
        print(f"\n✓ Expected error: {e}")
        print("   The discover() function does not exist in the codebase.")
        print("   This confirms the analysis finding.\n")
        return True
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("django-udp-discovery-client: Current Capabilities Test")
    print("=" * 60 + "\n")
    
    results = []
    results.append(("Configuration", test_config()))
    results.append(("Interfaces", test_interfaces()))
    results.append(("Discover Function", test_discover_function()))
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("""
The library currently provides:
  ✓ Configuration system (fully functional)
  ✓ Network interface enumeration (requires netifaces/ifaddr)
  ✗ Discovery functionality (NOT IMPLEMENTED)

The discover() function advertised in README does not exist.
See ANALYSIS.md for complete details.
    """)


if __name__ == "__main__":
    main()
