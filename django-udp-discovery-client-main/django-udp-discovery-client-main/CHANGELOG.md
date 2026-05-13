# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-15

### Changed

- First production release; PyPI-ready.
- README overhaul: Table of Contents, Features, Technical Considerations, clear installation variants (`pip install` vs `pip install ...[network]`).
- No functional changes from 0.1.0.

## [0.1.0] - 2025-01-XX

### Added

#### Core Discovery Features
- **UDP Broadcast Discovery**: Full implementation of `discover()` and `discover_one()` functions
  - Multi-interface discovery across all network interfaces
  - Automatic broadcast address computation from interface IP and netmask
  - Result deduplication by (ip, port)
  - Graceful error handling with comprehensive logging

#### Network Interface Support
- **Interface Enumeration**: Cross-platform network interface detection (`get_interfaces()`)
- **Interface Filtering**: Whitelist and blacklist support for interface selection (`select_interfaces()`)
- **Network Utilities**: 
  - Netmask to CIDR prefix conversion (`netmask_to_prefix()`)
  - CIDR prefix to netmask conversion (`prefix_to_netmask()`)
  - Network range calculation (`network_from_ip_and_mask()`)
  - Broadcast address calculation (`broadcast_from_ip_and_mask()`)

#### Configuration System
- **ClientConfig**: Comprehensive configuration dataclass with validation
- **Environment Variable Support**: Load configuration from environment variables
- **Runtime Configuration**: Override configuration at runtime
- **Configuration Options**:
  - Discovery port (default: 9999)
  - Discovery message (default: "DISCOVER_SERVER")
  - Response prefix (default: "SERVER_IP:")
  - Timeout configuration
  - Interface whitelist/blacklist

#### Discovery Protocol
- **Protocol Implementation**: Full support for `django-udp-discovery` protocol
  - Sends `DISCOVER_SERVER` messages via UDP broadcast
  - Parses `SERVER_IP:<ip>:<port>` responses
  - Compatible with `django-udp-discovery` servers

#### Result Handling
- **DiscoveryResult**: Dataclass for discovered server information
  - IP address and port
  - Raw response bytes
  - Optional metadata dictionary

#### Error Handling & Logging
- **Comprehensive Logging**: Module-level logger (`django_udp_discovery_client`)
  - DEBUG: Detailed socket operations and interface selection
  - INFO: Discovery start/stop and servers found
  - WARNING: Invalid responses and interface failures
  - ERROR: Socket errors and network failures
- **Graceful Failure**: Discovery functions return empty lists/None instead of raising exceptions
- **Error Recovery**: Network errors are logged but don't crash the application

#### Optional Django Integration
- **Django Management Command**: `python manage.py discover_servers`
  - Discover servers from Django projects
  - Formatted table output
  - Command-line argument support for all configuration options
  - Verbose mode for detailed output
- **Django App**: `discovery_client_django` app for Django integration
  - Add to `INSTALLED_APPS` to enable management command
  - Optional dependency (core library works without Django)

#### Testing
- **Unit Tests**: Comprehensive test coverage for all components
  - Network utility function tests
  - Discovery API tests
  - Interface filtering tests
  - UDP discovery tests
  - Multi-interface discovery tests
  - Error handling and logging tests
- **Integration Tests**: End-to-end tests with mock UDP server
  - MockDiscoveryServer helper class
  - Tests for single server discovery
  - Tests for multiple servers
  - Tests for timeout and error scenarios

#### Documentation
- **README.md**: Complete user documentation
  - Installation instructions
  - Quick start guide
  - Usage examples
  - Django integration guide
  - Logging configuration
  - Interface filtering documentation
- **API Documentation**: Comprehensive API reference in `info.md`
- **Code Documentation**: Docstrings for all public APIs

### Technical Details

#### Dependencies
- **Core**: Python >= 3.8 (standard library only)
- **Optional Network**: `netifaces>=0.11.0` or `ifaddr>=0.2.0` for interface enumeration
- **Optional Django**: `Django>=3.2` for Django integration

#### Platform Support
- Windows
- Linux
- macOS

#### Architecture
- Pure Python library (no Django required for core functionality)
- Modular design with separate packages for:
  - Core discovery (`discovery_client`)
  - Network utilities (`discovery_client.network`)
  - Django integration (`discovery_client_django`)
- Clean separation of concerns

### Compatibility

- **django-udp-discovery**: Fully compatible with `django-udp-discovery` servers
  - Uses same discovery protocol (DISCOVER_SERVER / SERVER_IP:)
  - Default port: 9999
  - Default response format: SERVER_IP:<ip>:<port>

### Known Limitations

- **Broadcast Only**: Currently uses UDP broadcast (multicast support planned)
- **VLAN / Segmented Networks**: UDP broadcast discovery typically does not cross routers and may only reach the local broadcast domain (commonly a `/24` segment). On corporate networks segmented into VLANs, servers on other segments may not be discoverable yet. Hybrid broadcast + unicast scanning is planned.
- **No Retry Logic**: Single discovery attempt per call (retry logic planned)
- **IPv4 Only**: IPv6 support not yet implemented

### Migration Notes

This is the first functional release. If you were using a previous development version:

- The `discover()` function is now fully implemented (previously was a stub)
- All configuration options are now functional
- Interface filtering is now implemented and working
- Error handling is now comprehensive

### Contributors

- Initial implementation and core features
- Django integration
- Testing infrastructure
- Documentation

---

## [Unreleased]

### Planned Features
- Multicast discovery support
- Configurable retry logic
- Advanced server filtering options
- IPv6 support
- Performance optimizations
