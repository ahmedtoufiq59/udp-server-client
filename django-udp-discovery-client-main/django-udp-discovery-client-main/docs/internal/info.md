# django-udp-discovery-client: Package Information

## Package Status

**Version**: 0.0.0 (Development/Pre-release)  
**Status**: ✅ **Functional** - Core discovery features implemented and working  
**Python**: >= 3.8  
**License**: MIT

---

## Current State

This package provides a **fully functional** UDP-based service discovery client for discovering `django-udp-discovery` servers on local networks. All core features are implemented and tested.

### ✅ What Works

- **UDP Discovery**: Full implementation of `discover()` and `discover_one()` functions
- **Multi-Interface Discovery**: Automatically discovers servers across all network interfaces
- **Server Detection**: Can discover and parse responses from `django-udp-discovery` servers
- **Configuration Management**: Full-featured configuration system with environment variable support
- **Network Interface Detection**: Cross-platform network interface enumeration with filtering
- **Network Utilities**: Netmask/prefix conversions and network calculations
- **Error Handling**: Robust error handling and logging throughout
- **Interface Filtering**: Whitelist/blacklist support for interface selection

### 🔄 Planned / Future Enhancements

- **Multicast Support**: Multicast discovery (currently uses broadcast only)
- **Retry Logic**: Configurable retry mechanisms for failed discovery attempts
- **Advanced Filtering**: More sophisticated server filtering and selection options

### 🎯 Optional Django Integration

- **Django Management Command**: `python manage.py discover_servers` command for discovering servers from Django projects
- **Django App**: `discovery_client_django` app that can be added to `INSTALLED_APPS`
- **Optional Dependency**: Django integration is optional - core library works without Django

---

## Package Capabilities

### 1. Configuration Management ✅

The package provides a robust configuration system for UDP discovery client settings.

**What it can do:**
- Define and validate discovery parameters (port, message, timeout, etc.)
- Load configuration from environment variables
- Override configuration at runtime
- Validate all configuration values

**Use cases:**
- Setting up discovery client parameters
- Environment-based configuration
- Runtime configuration overrides

### 2. Network Interface Enumeration ✅

The package can detect and enumerate network interfaces on the local machine.

**What it can do:**
- List all active IPv4 network interfaces
- Get IP addresses, netmasks, and broadcast addresses
- Filter out loopback interfaces automatically
- Work cross-platform (Windows, Linux, macOS)

**Use cases:**
- Network diagnostics
- Finding available network interfaces
- Getting broadcast addresses for network operations
- Network configuration analysis

### 3. Network Utility Functions ✅

The package provides utilities for network address calculations.

**What it can do:**
- Convert between netmask and CIDR prefix notation
- Calculate network ranges from IP and mask
- Compute broadcast addresses
- Validate network configurations

**Use cases:**
- Network address calculations
- Subnet analysis
- Network configuration validation
- IP address manipulation

### 4. UDP Server Discovery ✅

The package can discover `django-udp-discovery` servers on local networks using UDP broadcast.

**What it can do:**
- Send UDP discovery requests to network interfaces
- Receive and parse server responses
- Discover servers across multiple network interfaces
- Deduplicate results automatically
- Filter interfaces using whitelist/blacklist
- Handle network errors gracefully

**Use cases:**
- Discovering Django servers running `django-udp-discovery`
- Finding services on local networks
- Service discovery in distributed systems
- Network service enumeration

**Protocol:**
- Discovery message: `"DISCOVER_SERVER"` (configurable)
- Response prefix: `"SERVER_IP:"` (configurable)
- Response format: `"SERVER_IP:<ip>:<port>"`

---

## Available APIs

### Main Package (`discovery_client`)

#### `ClientConfig` (Class) ✅ **FUNCTIONAL

Configuration dataclass for UDP discovery client settings.

```python
from discovery_client import ClientConfig

# Create with defaults
config = ClientConfig()

# Create with custom values
config = ClientConfig(
    discovery_port=8888,
    timeout=10.0,
    retries=5
)
```

**Attributes:**
- `discovery_port: int` - UDP port for discovery (default: 9999)
- `discovery_message: bytes` - Message to send (default: b"DISCOVER_SERVER")
- `response_prefix: bytes` - Expected response prefix (default: b"SERVER_IP:")
- `timeout: float` - Timeout in seconds (default: 5.0)
- `retries: int` - Number of retry attempts (default: 3)
- `enable_subnet_scan: bool` - Enable subnet scanning (default: True)
- `interfaces_whitelist: Optional[List[str]]` - Interface whitelist (default: None)
- `interfaces_blacklist: Optional[List[str]]` - Interface blacklist (default: None)

**Methods:**
- `from_env(**overrides) -> ClientConfig` - Create from environment variables

**Validation:**
- Port range: 1-65535
- Timeout must be positive
- Retries must be non-negative
- Message and prefix are normalized to bytes

---

#### `load_config(**kwargs) -> ClientConfig` ✅ **FUNCTIONAL

Load and validate configuration with optional overrides.

```python
from discovery_client import load_config

# Load with defaults and environment variables
config = load_config()

# Override specific values
config = load_config(timeout=10.0, discovery_port=8888)
```

**Parameters:**
- `**kwargs` - Runtime overrides (take precedence over env vars)

**Returns:**
- `ClientConfig` instance

**Environment Variables:**
- `DISCOVERY_CLIENT_PORT` - Discovery port
- `DISCOVERY_CLIENT_MESSAGE` - Discovery message
- `DISCOVERY_CLIENT_RESPONSE_PREFIX` - Response prefix
- `DISCOVERY_CLIENT_TIMEOUT` - Timeout in seconds
- `DISCOVERY_CLIENT_RETRIES` - Number of retries
- `DISCOVERY_CLIENT_ENABLE_SUBNET_SCAN` - Enable subnet scan (bool)
- `DISCOVERY_CLIENT_INTERFACES_WHITELIST` - Comma-separated interface names
- `DISCOVERY_CLIENT_INTERFACES_BLACKLIST` - Comma-separated interface names

---

#### `DiscoveryResult` (Dataclass) ✅ **FUNCTIONAL

Result object returned by discovery functions.

```python
from discovery_client import DiscoveryResult

# Created automatically by discover() and discover_one()
result = DiscoveryResult(
    ip="192.168.1.100",
    port=8000,
    raw_response=b"SERVER_IP:192.168.1.100:8000",
    extra={"source_address": "192.168.1.100"}
)
```

**Attributes:**
- `ip: str` - Server IPv4 address
- `port: int` - Server port number
- `raw_response: bytes` - Raw response bytes received from server
- `extra: Optional[dict]` - Additional metadata (e.g., source address)

**Validation:**
- IP must be valid IPv4 address
- Port must be in range 1-65535
- Raw response must be bytes

---

#### `discover(config: Optional[ClientConfig] = None) -> List[DiscoveryResult]` ✅ **FUNCTIONAL

Discover all `django-udp-discovery` servers on the local network.

```python
from discovery_client import discover, ClientConfig

# Use default configuration
servers = discover()

# Use custom configuration
config = ClientConfig(timeout=10.0, discovery_port=9999)
servers = discover(config=config)

# Process results
for server in servers:
    print(f"Found: {server.ip}:{server.port}")
```

**Parameters:**
- `config: Optional[ClientConfig]` - Configuration instance (uses defaults if None)

**Returns:**
- `List[DiscoveryResult]` - List of discovered servers (empty list if none found)

**Behavior:**
- Sends UDP broadcast discovery requests to all selected network interfaces
- Collects responses until timeout
- Deduplicates results by (ip, port)
- Returns empty list on network errors (errors are logged)

**Protocol:**
- Sends: `"DISCOVER_SERVER"` (configurable via `ClientConfig.discovery_message`)
- Expects: Responses starting with `"SERVER_IP:"` (configurable via `ClientConfig.response_prefix`)
- Parses: `"SERVER_IP:<ip>:<port>"` format

---

#### `discover_one(config: Optional[ClientConfig] = None) -> Optional[DiscoveryResult]` ✅ **FUNCTIONAL

Discover a single `django-udp-discovery` server (returns first found).

```python
from discovery_client import discover_one

# Discover first server
server = discover_one()
if server:
    print(f"Found server at {server.ip}:{server.port}")
else:
    print("No servers found")
```

**Parameters:**
- `config: Optional[ClientConfig]` - Configuration instance (uses defaults if None)

**Returns:**
- `Optional[DiscoveryResult]` - First discovered server, or None if none found

**Behavior:**
- Wrapper around `discover()` that returns the first result
- Returns None if no servers are found or on network errors
- Same timeout and error handling as `discover()`

---

### Network Module (`discovery_client.network`)

#### `get_interfaces() -> List[InterfaceInfo]` ✅ **FUNCTIONAL

Enumerate all active IPv4 network interfaces.

```python
from discovery_client.network.interfaces import get_interfaces

interfaces = get_interfaces()
for iface in interfaces:
    print(f"{iface.name}: {iface.ip}/{iface.netmask} -> {iface.broadcast}")
```

**Returns:**
- `List[InterfaceInfo]` - List of interface information objects

**Raises:**
- `ImportError` - If neither `netifaces` nor `ifaddr` is available

**Dependencies:**
- Requires `netifaces>=0.11.0` OR `ifaddr>=0.2.0`
- Install with: `pip install django-udp-discovery-client[network]`

**Features:**
- Automatically filters loopback interfaces
- Computes broadcast addresses if missing
- Cross-platform support (Windows, Linux, macOS)
- Prefers `netifaces`, falls back to `ifaddr`

---

#### `InterfaceInfo` (Dataclass) ✅ **FUNCTIONAL

Information about a network interface.

```python
from discovery_client.network.interfaces import InterfaceInfo

# Attributes
iface.name        # Interface name (e.g., 'eth0', 'en0', 'Ethernet')
iface.ip          # IPv4 address (e.g., '192.168.1.100')
iface.netmask     # Netmask (e.g., '255.255.255.0')
iface.broadcast   # Broadcast address (e.g., '192.168.1.255')
```

**Attributes:**
- `name: str` - Interface name
- `ip: str` - IPv4 address
- `netmask: str` - Netmask in dotted decimal format
- `broadcast: Optional[str]` - Broadcast address (computed if None)

---

#### `netmask_to_prefix(netmask: str) -> int` ✅ **FUNCTIONAL

Convert netmask to CIDR prefix length.

```python
from discovery_client.network import netmask_to_prefix

prefix = netmask_to_prefix("255.255.255.0")  # Returns 24
prefix = netmask_to_prefix("255.0.0.0")       # Returns 8
```

**Parameters:**
- `netmask: str` - Netmask in dotted decimal format (e.g., "255.255.255.0")

**Returns:**
- `int` - CIDR prefix length (0-32)

**Raises:**
- `ValueError` - If netmask is invalid or non-contiguous

**Examples:**
- `"255.255.255.0"` → `24`
- `"255.255.0.0"` → `16`
- `"255.0.0.0"` → `8`
- `"255.255.255.248"` → `29`

---

#### `prefix_to_netmask(prefix: int) -> str` ✅ **FUNCTIONAL

Convert CIDR prefix length to netmask.

```python
from discovery_client.network import prefix_to_netmask

netmask = prefix_to_netmask(24)  # Returns "255.255.255.0"
netmask = prefix_to_netmask(8)    # Returns "255.0.0.0"
```

**Parameters:**
- `prefix: int` - CIDR prefix length (0-32)

**Returns:**
- `str` - Netmask in dotted decimal format

**Raises:**
- `ValueError` - If prefix is out of valid range (0-32)

**Examples:**
- `24` → `"255.255.255.0"`
- `16` → `"255.255.0.0"`
- `8` → `"255.0.0.0"`
- `29` → `"255.255.255.248"`

---

#### `network_from_ip_and_mask(ip: str, mask: Union[str, int]) -> ipaddress.IPv4Network` ✅ **FUNCTIONAL

Create IPv4Network object from IP address and netmask.

```python
from discovery_client.network import network_from_ip_and_mask

# With netmask string
network = network_from_ip_and_mask("192.168.1.100", "255.255.255.0")
# Returns: IPv4Network('192.168.1.0/24')

# With prefix length
network = network_from_ip_and_mask("10.0.0.1", 8)
# Returns: IPv4Network('10.0.0.0/8')

# With prefix string
network = network_from_ip_and_mask("172.16.0.1", "/16")
# Returns: IPv4Network('172.16.0.0/16')
```

**Parameters:**
- `ip: str` - IPv4 address (e.g., "192.168.1.100")
- `mask: Union[str, int]` - Netmask string, prefix int, or prefix string like "/24"

**Returns:**
- `ipaddress.IPv4Network` - Network object

**Raises:**
- `ValueError` - If IP or mask is invalid
- `TypeError` - If mask is not str or int

---

#### `broadcast_from_ip_and_mask(ip: str, mask: Union[str, int]) -> str` ✅ **FUNCTIONAL

Calculate broadcast address from IP address and netmask.

```python
from discovery_client.network import broadcast_from_ip_and_mask

# With netmask string
broadcast = broadcast_from_ip_and_mask("192.168.1.100", "255.255.255.0")
# Returns: "192.168.1.255"

# With prefix length
broadcast = broadcast_from_ip_and_mask("10.0.0.1", 8)
# Returns: "10.255.255.255"
```

**Parameters:**
- `ip: str` - IPv4 address
- `mask: Union[str, int]` - Netmask string, prefix int, or prefix string

**Returns:**
- `str` - Broadcast address

**Raises:**
- `ValueError` - If IP or mask is invalid

---

## API Summary Table

| API | Module | Status | Description |
|-----|--------|--------|-------------|
| `ClientConfig` | `discovery_client` | ✅ Functional | Configuration dataclass |
| `load_config()` | `discovery_client` | ✅ Functional | Load configuration with env var support |
| `DiscoveryResult` | `discovery_client` | ✅ Functional | Discovery result dataclass |
| `discover()` | `discovery_client` | ✅ **FUNCTIONAL** | Discover all servers on network |
| `discover_one()` | `discovery_client` | ✅ **FUNCTIONAL** | Discover single server (returns first found) |
| `get_interfaces()` | `discovery_client.network.interfaces` | ✅ Functional | Enumerate network interfaces |
| `select_interfaces()` | `discovery_client.network.interfaces` | ✅ Functional | Filter interfaces by whitelist/blacklist |
| `InterfaceInfo` | `discovery_client.network.interfaces` | ✅ Functional | Interface information dataclass |
| `netmask_to_prefix()` | `discovery_client.network` | ✅ Functional | Convert netmask to prefix |
| `prefix_to_netmask()` | `discovery_client.network` | ✅ Functional | Convert prefix to netmask |
| `network_from_ip_and_mask()` | `discovery_client.network` | ✅ Functional | Create network object |
| `broadcast_from_ip_and_mask()` | `discovery_client.network` | ✅ Functional | Calculate broadcast address |

### Django Integration (`discovery_client_django`)

| API | Module | Status | Description |
|-----|--------|--------|-------------|
| `discovery_client_django` | `discovery_client_django` | ✅ Functional | Django app for optional integration |
| `discover_servers` | `discovery_client_django.management.commands` | ✅ Functional | Django management command |

**Django Management Command:**
- `python manage.py discover_servers` - Discover servers from Django project
- Supports all `ClientConfig` options via command-line arguments
- Prints formatted table of discovered servers

---

## Usage Examples

### Example 1: Configuration Management

```python
from discovery_client import ClientConfig, load_config

# Method 1: Direct instantiation
config = ClientConfig(
    discovery_port=8888,
    timeout=10.0,
    retries=5
)

# Method 2: From environment variables
# Set: DISCOVERY_CLIENT_PORT=8888
# Set: DISCOVERY_CLIENT_TIMEOUT=10.0
config = load_config()

# Method 3: Override environment variables
config = load_config(timeout=15.0)  # Overrides env var
```

### Example 2: Network Interface Enumeration

```python
from discovery_client.network.interfaces import get_interfaces, InterfaceInfo

try:
    interfaces = get_interfaces()
    print(f"Found {len(interfaces)} network interface(s):")
    
    for iface in interfaces:
        print(f"  {iface.name}:")
        print(f"    IP: {iface.ip}")
        print(f"    Netmask: {iface.netmask}")
        print(f"    Broadcast: {iface.broadcast}")
except ImportError:
    print("Install network dependencies: pip install django-udp-discovery-client[network]")
```

### Example 3: Network Utilities

```python
from discovery_client.network import (
    netmask_to_prefix,
    prefix_to_netmask,
    network_from_ip_and_mask,
    broadcast_from_ip_and_mask,
)

# Convert netmask to prefix
prefix = netmask_to_prefix("255.255.255.0")  # 24

# Convert prefix to netmask
netmask = prefix_to_netmask(24)  # "255.255.255.0"

# Create network object
network = network_from_ip_and_mask("192.168.1.100", "255.255.255.0")
print(network)  # 192.168.1.0/24

# Calculate broadcast
broadcast = broadcast_from_ip_and_mask("192.168.1.100", 24)
print(broadcast)  # 192.168.1.255
```

### Example 4: Server Discovery

```python
from discovery_client import discover, discover_one, ClientConfig, DiscoveryResult

# Discover all servers on the network
servers = discover()
print(f"Found {len(servers)} server(s):")
for server in servers:
    print(f"  - {server.ip}:{server.port}")
    print(f"    Raw response: {server.raw_response}")

# Discover just one server (returns first found)
server = discover_one()
if server:
    print(f"Found server at {server.ip}:{server.port}")
    server_url = f"http://{server.ip}:{server.port}"
    print(f"Server URL: {server_url}")
else:
    print("No servers found")

# Custom configuration
config = ClientConfig(
    timeout=10.0,  # Wait up to 10 seconds
    discovery_port=9999,  # Discovery port
    interfaces_whitelist=["eth0", "wlan0"]  # Only use specific interfaces
)
servers = discover(config=config)
print(f"Found {len(servers)} server(s) with custom config")
```

### Example 5: Complete Workflow

```python
from discovery_client import load_config
from discovery_client.network.interfaces import get_interfaces
from discovery_client.network import netmask_to_prefix, broadcast_from_ip_and_mask

# Load configuration
config = load_config(timeout=5.0)

# Get network interfaces
interfaces = get_interfaces()

# Process each interface
for iface in interfaces:
    # Convert netmask to prefix
    prefix = netmask_to_prefix(iface.netmask)
    
    # Calculate broadcast (if not already set)
    if not iface.broadcast:
        broadcast = broadcast_from_ip_and_mask(iface.ip, iface.netmask)
    else:
        broadcast = iface.broadcast
    
    print(f"Interface: {iface.name}")
    print(f"  Network: {iface.ip}/{prefix}")
    print(f"  Broadcast: {broadcast}")
    print(f"  Discovery port: {config.discovery_port}")
```

---

## Dependencies

### Core Dependencies
- **Python**: >= 3.8
- **Standard Library**: `ipaddress`, `dataclasses`, `typing`, `os`

### Optional Dependencies (for `get_interfaces()`)
- `netifaces>=0.11.0` (preferred)
- `ifaddr>=0.2.0` (fallback)

**Installation:**
```bash
pip install django-udp-discovery-client[network]
```

---

## What This Package CAN Do

✅ **Manage configuration** - Full configuration system with validation  
✅ **Detect network interfaces** - Enumerate active network interfaces  
✅ **Calculate network addresses** - Convert masks, compute networks and broadcasts  
✅ **Validate network configs** - Validate IP addresses, netmasks, and network ranges  
✅ **Cross-platform support** - Works on Windows, Linux, and macOS  

---

## Development Status

### Completed ✅
- Configuration system (`ClientConfig`, `load_config`)
- Network interface enumeration (`get_interfaces`, `select_interfaces`)
- Network utility functions (mask/prefix conversions, network calculations)
- **Core discovery functions** (`discover()`, `discover_one()`)
- **UDP socket management** (broadcast discovery, multi-interface support)
- **Response parsing** (SERVER_IP: protocol parsing)
- **Server discovery logic** (multi-interface, deduplication)
- **Error handling and logging** (comprehensive error handling throughout)
- **Interface filtering** (whitelist/blacklist support)
- Unit tests for network utilities
- Unit tests for discovery functions
- Integration tests with mock UDP server

### In Progress 🚧
- None currently

### Planned 📋
- Multicast discovery support
- Configurable retry logic
- Advanced server filtering options
- Performance optimizations

---

## Installation

```bash
# Basic installation (pure Python, no Django required)
pip install django-udp-discovery-client

# With network dependencies (required for get_interfaces)
pip install django-udp-discovery-client[network]

# With Django integration (management command)
pip install django-udp-discovery-client[django]

# With all optional dependencies
pip install django-udp-discovery-client[all]

# Development installation
git clone https://github.com/Ogro-Projukti/django-udp-discovery-client.git
cd django-udp-discovery-client
pip install -e ".[network,django]"
```

---

## Testing

```bash
# Run network utility tests
pytest tests/test_network_utils.py -v

# Run all tests (when available)
pytest tests/ -v
```

---

## Contributing

This package is in early development. Contributions are welcome for:
- Core discovery implementation
- UDP socket management
- Response parsing
- Error handling
- Additional tests
- Documentation improvements

---

## License

MIT License - see LICENSE file for details.

---

## Repository

https://github.com/Ogro-Projukti/django-udp-discovery-client

---

**Last Updated**: Documentation updated to reflect implemented features  
**Package Version**: 0.0.0  
**Status**: ✅ Functional - Core discovery features implemented and working
