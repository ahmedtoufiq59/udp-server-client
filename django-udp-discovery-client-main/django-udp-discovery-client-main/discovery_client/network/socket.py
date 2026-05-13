"""
UDP socket layer for discovery_client.

Low-level operations: create broadcast socket, send discovery message,
receive and parse SERVER_IP: responses, multi-interface broadcast discovery,
segmented-network detection, and formatted warning message for callers.
"""
import logging
import ipaddress
import socket
from typing import List, Tuple, Optional, Set
from discovery_client.config import ClientConfig
from discovery_client.results import DiscoveryResult
from discovery_client.network.interfaces import InterfaceInfo, select_interfaces
from discovery_client.network.utils import broadcast_from_ip_and_mask

# Module-level logger
logger = logging.getLogger("django_udp_discovery_client")


# Default broadcast address for single broadcast discovery
DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"


def parse_response(response: bytes, prefix: bytes) -> Optional[Tuple[str, int]]:
    """
    Parse a discovery response to extract IP and port.
    
    Expected format: "SERVER_IP:<ip>[:port]"
    Examples:
        - "SERVER_IP:192.168.1.100:8000" -> ("192.168.1.100", 8000)
        - "SERVER_IP:192.168.1.100" -> ("192.168.1.100", 8000)  # default port
    
    Args:
        response: Raw bytes received from server
        prefix: Expected response prefix (e.g., b"SERVER_IP:")
    
    Returns:
        Tuple of (ip, port) if parsing succeeds, None otherwise.
        Port defaults to 8000 if not specified in response.
    
    Example:
        >>> parse_response(b"SERVER_IP:192.168.1.100:8000", b"SERVER_IP:")
        ('192.168.1.100', 8000)
        >>> parse_response(b"SERVER_IP:10.0.0.5", b"SERVER_IP:")
        ('10.0.0.5', 8000)
    """
    if not response.startswith(prefix):
        return None
    
    # Extract the part after the prefix
    try:
        content = response[len(prefix):].decode('utf-8', errors='ignore').strip()
    except (UnicodeDecodeError, AttributeError):
        return None
    
    # Parse IP and optional port
    # Format: <ip>[:port]
    if ':' in content:
        parts = content.split(':', 1)
        ip_str = parts[0].strip()
        try:
            port = int(parts[1].strip())
            if not (1 <= port <= 65535):
                return None
        except (ValueError, IndexError):
            return None
    else:
        ip_str = content.strip()
        port = 8000  # Default port for django-udp-discovery
    
    # Basic IP validation
    if not ip_str:
        return None
    
    # Validate IP format (basic check - more thorough validation can be added)
    try:
        parts = ip_str.split('.')
        if len(parts) != 4:
            return None
        for part in parts:
            num = int(part)
            if not (0 <= num <= 255):
                return None
    except (ValueError, AttributeError):
        return None
    
    return (ip_str, port)


def create_discovery_socket(timeout: float) -> socket.socket:
    """
    Create and configure a UDP socket for discovery.
    
    Args:
        timeout: Socket timeout in seconds
    
    Returns:
        Configured UDP socket with broadcast enabled
    
    Raises:
        OSError: If socket creation or configuration fails
    """
    try:
        logger.debug(f"Creating UDP discovery socket with timeout={timeout}s")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Enable broadcast
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        logger.debug("Socket broadcast enabled")
        
        # Set timeout
        sock.settimeout(timeout)
        logger.debug(f"Socket timeout set to {timeout}s")
        
        return sock
    except OSError as e:
        logger.error(f"Failed to create discovery socket: {e}", exc_info=True)
        raise


def send_discovery_request(
    sock: socket.socket,
    message: bytes,
    port: int,
    broadcast_address: str = DEFAULT_BROADCAST_ADDRESS
) -> None:
    """
    Send a UDP discovery request to the broadcast address.
    
    Args:
        sock: UDP socket (must have SO_BROADCAST enabled)
        message: Discovery message to send (e.g., b"DISCOVER_SERVER")
        port: UDP port to send to
        broadcast_address: Broadcast address (default: "255.255.255.255")
    
    Raises:
        OSError: If send fails
    """
    try:
        logger.info(f"Sending discovery request to {broadcast_address}:{port}")
        logger.debug(f"Discovery message: {message!r}")
        sock.sendto(message, (broadcast_address, port))
        logger.debug(f"Discovery request sent successfully to {broadcast_address}:{port}")
    except OSError as e:
        logger.error(
            f"Failed to send discovery request to {broadcast_address}:{port}: {e}",
            exc_info=True
        )
        raise


def receive_responses(
    sock: socket.socket,
    config: ClientConfig,
    max_responses: Optional[int] = None
) -> List[DiscoveryResult]:
    """
    Receive and parse discovery responses until timeout.
    
    Args:
        sock: UDP socket with timeout set
        config: ClientConfig with response_prefix for parsing
        max_responses: Maximum number of responses to collect (None = unlimited)
    
    Returns:
        List of DiscoveryResult objects for valid responses
    
    Note:
        This function will continue receiving until socket timeout.
        Invalid responses (wrong prefix) are silently ignored.
    """
    results = []
    logger.debug("Starting to receive discovery responses")
    
    while True:
        try:
            # Receive response
            data, addr = sock.recvfrom(4096)  # Max UDP packet size is typically 65507
            logger.debug(f"Received response from {addr[0]}:{addr[1]}: {data!r}")
            
            # Parse response
            parsed = parse_response(data, config.response_prefix)
            if parsed is None:
                # Invalid response, ignore
                logger.warning(
                    f"Received invalid response from {addr[0]}:{addr[1]}: "
                    f"does not start with prefix {config.response_prefix!r}"
                )
                continue
            
            ip, port = parsed
            logger.info(f"Parsed valid response: server at {ip}:{port}")
            
            # Create DiscoveryResult
            try:
                result = DiscoveryResult(
                    ip=ip,
                    port=port,
                    raw_response=data,
                    extra={"source_address": addr[0]}  # Store source IP for reference
                )
                results.append(result)
                logger.debug(f"Added discovered server: {ip}:{port}")
                
                # Check if we've reached max responses
                if max_responses is not None and len(results) >= max_responses:
                    logger.debug(f"Reached max responses limit ({max_responses})")
                    break
                    
            except ValueError as e:
                # Invalid DiscoveryResult (e.g., invalid IP/port), ignore
                logger.warning(
                    f"Failed to create DiscoveryResult from parsed response "
                    f"({ip}:{port}): {e}"
                )
                continue
                
        except socket.timeout:
            # Timeout reached, stop receiving
            logger.info(f"Discovery timeout reached. Found {len(results)} server(s)")
            break
        except OSError as e:
            # Socket error, stop receiving
            logger.error(f"Socket error while receiving responses: {e}", exc_info=True)
            break
    
    logger.info(f"Discovery complete: {len(results)} server(s) found")
    return results


def discover_servers_single_broadcast(
    config: ClientConfig,
    broadcast_address: str = DEFAULT_BROADCAST_ADDRESS
) -> List[DiscoveryResult]:
    """
    Perform UDP discovery using a single broadcast address.
    
    This is the core discovery function that:
    1. Creates a UDP socket with broadcast enabled
    2. Sends discovery message to broadcast address
    3. Receives and parses responses until timeout
    4. Returns list of discovered servers
    
    Args:
        config: ClientConfig with discovery settings
        broadcast_address: Broadcast address to use (default: "255.255.255.255")
    
    Returns:
        List of DiscoveryResult objects for discovered servers.
        Returns empty list if no servers respond or timeout occurs.
    
    Raises:
        OSError: If socket operations fail
    
    Example:
        >>> from discovery_client import ClientConfig
        >>> config = ClientConfig(timeout=5.0)
        >>> servers = discover_servers_single_broadcast(config)
        >>> for server in servers:
        ...     print(f"Found: {server.ip}:{server.port}")
    """
    logger.info("Starting single broadcast discovery")
    logger.debug(f"Broadcast address: {broadcast_address}, port: {config.discovery_port}")
    
    sock = None
    try:
        # Create and configure socket
        sock = create_discovery_socket(config.timeout)
        
        # Send discovery request
        send_discovery_request(
            sock,
            config.discovery_message,
            config.discovery_port,
            broadcast_address
        )
        
        # Receive responses
        results = receive_responses(sock, config)
        
        return results
        
    except OSError as e:
        logger.error(f"Network error during discovery: {e}", exc_info=True)
        raise
    finally:
        # Clean up socket
        if sock is not None:
            try:
                sock.close()
                logger.debug("Discovery socket closed")
            except OSError as e:
                logger.warning(f"Error closing socket: {e}")


def get_interface_broadcast(iface: InterfaceInfo) -> str:
    """
    Get broadcast address for an interface.
    
    Uses the interface's broadcast address if present, otherwise computes it
    from the interface's IP and netmask.
    
    Args:
        iface: InterfaceInfo object
    
    Returns:
        Broadcast address as string
    
    Raises:
        ValueError: If broadcast cannot be computed (invalid IP/netmask)
    """
    if iface.broadcast:
        logger.debug(f"Using broadcast address from interface {iface.name}: {iface.broadcast}")
        return iface.broadcast
    
    # Compute broadcast from IP and netmask
    try:
        broadcast = broadcast_from_ip_and_mask(iface.ip, iface.netmask)
        logger.debug(f"Computed broadcast address for interface {iface.name}: {broadcast}")
        return broadcast
    except ValueError as e:
        logger.error(
            f"Failed to compute broadcast address for interface {iface.name} "
            f"({iface.ip}/{iface.netmask}): {e}",
            exc_info=True
        )
        raise


def detect_segmented_network(interfaces: List[InterfaceInfo]) -> Optional[dict]:
    """
    Detect if the network is a large segmented network that may not work with
    current broadcast-based discovery.
    
    Large subnets (prefix < 24) are often segmented into /24 VLANs, and
    UDP broadcasts only reach devices in the same broadcast domain. This
    function detects such networks and returns information about the issue.
    
    This function is OS-independent and uses only standard Python libraries:
    - ipaddress module (Python 3.3+ standard library)
    - Standard IP address parsing and network calculations
    - Works on Windows, Linux, macOS, and other platforms
    
    Detection criteria (all must be true to trigger warning):
    1. Network prefix < 24 (large subnet)
    2. Network is in corporate range (10.x.x.x or 172.16-31.x.x)
    3. Broadcast domain differs from calculated broadcast (indicates segmentation)
    
    Networks that are NOT flagged:
    - /24 networks (typical for mobile hotspots, home networks) - these work fine
    - 192.168.x.x networks with /24 or smaller - typically not segmented
    - Networks where broadcast domain matches calculated broadcast
    
    Args:
        interfaces: List of InterfaceInfo objects to check
    
    Returns:
        Dictionary with detection results if segmented network detected, None otherwise.
        Contains keys: 'interface', 'ip', 'network', 'prefix', 'total_hosts',
        'calculated_broadcast', 'likely_broadcast_domain', 'is_corporate', 'segments'
    
    Note:
        Detection is based on network topology (subnet size and IP ranges),
        not OS-specific features. Works identically across all platforms.
    """
    for iface in interfaces:
        # Skip link-local addresses (169.254.x.x)
        if iface.ip.startswith("169.254"):
            continue
        
        # Skip virtual/hypervisor networks that are typically not problematic
        # These are usually isolated and work fine with broadcast
        if any(virtual in iface.name.lower() for virtual in ['hyper-v', 'virtual', 'vmware', 'virtualbox', 'docker']):
            # But only skip if it's a /24 or smaller (not a large segmented network)
            try:
                network = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
                if network.prefixlen >= 24:
                    continue  # Skip virtual networks with /24 or smaller
            except:
                continue
        
        try:
            # Parse network from IP and netmask
            network = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
            prefix = network.prefixlen
            total_hosts = network.num_addresses
            
            # Only check large subnets (prefix < 24) - /24 networks work fine
            # Mobile hotspots and home networks typically use /24, so we skip those
            if prefix < 24:
                # Skip 192.168.x.x networks entirely - these are typically home/mobile hotspot networks
                # that work fine with broadcast discovery, even if they have large subnets
                if iface.ip.startswith("192.168."):
                    continue  # Skip mobile hotspot/home networks - they work fine
                
                # Calculate what the actual broadcast domain likely is (/24)
                network_24 = ipaddress.IPv4Network(f"{iface.ip}/24", strict=False)
                actual_broadcast_domain = str(network_24.broadcast_address)
                calculated_broadcast = iface.broadcast
                
                # Check if it's a corporate network (RFC 1918 private IP ranges)
                # This detection is OS-independent and works on all platforms
                is_corporate = False
                try:
                    ip_parts = iface.ip.split(".")
                    if len(ip_parts) >= 2:
                        if iface.ip.startswith("10."):
                            # 10.0.0.0/8 - Class A private network (commonly corporate)
                            is_corporate = True
                        elif iface.ip.startswith("172."):
                            # 172.16.0.0/12 - Class B private network (172.16.0.0 to 172.31.255.255)
                            second_octet = int(ip_parts[1])
                            if 16 <= second_octet <= 31:
                                is_corporate = True
                        # Note: 192.168.x.x is explicitly skipped above - these are home/mobile hotspot
                except (ValueError, IndexError):
                    # If IP parsing fails, continue without corporate detection
                    # This is OS-independent - just skip this check
                    pass
                
                # Only warn if:
                # 1. It's a corporate network (10.x.x.x or 172.16-31.x.x)
                # 2. AND the broadcast domain differs from calculated broadcast (indicates segmentation)
                # This ensures we don't warn about mobile hotspots (192.168.x.x) or simple networks
                if is_corporate and actual_broadcast_domain != calculated_broadcast:
                    return {
                        'interface': iface.name,
                        'ip': iface.ip,
                        'network': str(network),
                        'prefix': prefix,
                        'total_hosts': total_hosts,
                        'calculated_broadcast': calculated_broadcast,
                        'likely_broadcast_domain': actual_broadcast_domain,
                        'is_corporate': is_corporate,
                        'segments': 2 ** (24 - prefix) if prefix < 24 else 1
                    }
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            # Skip interfaces with invalid network configuration
            continue
    
    return None


def format_segmented_network_warning(segmented_info: dict, width: int = 40) -> str:
    """
    Format the "Segmented Network Detected" diagnostic message for display.
    Used by management command and sanity_check to print exactly once per run.
    """
    sep = "=" * width
    return (
        f"{sep}\n"
        "WARNING: Segmented Network Detected\n"
        f"{sep}\n"
        f"Interface: {segmented_info['interface']} ({segmented_info['ip']})\n"
        f"Network: {segmented_info['network']} ({segmented_info['total_hosts']:,} hosts)\n"
        f"Calculated broadcast: {segmented_info['calculated_broadcast']}\n"
        f"Likely broadcast domain: {segmented_info['likely_broadcast_domain']}\n"
        f"Network may be segmented into {segmented_info['segments']} /24 segments (VLANs).\n\n"
        "ISSUE: The current implementation uses UDP broadcast discovery, which only\n"
        "reaches devices in the same broadcast domain (typically /24 segment).\n"
        "If servers are on different network segments, they will NOT be discovered.\n\n"
        "LIMITATION: This module is not ready to handle segmented networks yet.\n"
        "Broadcast packets may only reach devices on the same /24 segment as your client.\n\n"
        "NOTE: No servers were found. This may be due to network segmentation.\n"
        "If servers are on a different network segment, they won't receive the broadcast.\n\n"
        "WORKAROUNDS:\n"
        "  1. Ensure servers are on the same /24 segment as the client\n"
        "  2. Use direct IP connection if server IP is known\n"
        "  3. Implement subnet scanning for known IP ranges\n"
        "  4. Contact network administrator for broadcast permissions\n"
        f"{sep}"
    )


def deduplicate_results(results: List[DiscoveryResult]) -> List[DiscoveryResult]:
    """
    Remove duplicate DiscoveryResult objects based on (ip, port) key.
    
    Keeps the first occurrence of each unique (ip, port) combination.
    
    Args:
        results: List of DiscoveryResult objects (may contain duplicates)
    
    Returns:
        List of unique DiscoveryResult objects (no duplicates by ip:port)
    
    Example:
        >>> results = [
        ...     DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response1"),
        ...     DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"response2"),
        ...     DiscoveryResult(ip="10.0.0.5", port=9000, raw_response=b"response3"),
        ... ]
        >>> unique = deduplicate_results(results)
        >>> len(unique)
        2
    """
    seen: Set[Tuple[str, int]] = set()
    unique_results = []
    
    for result in results:
        key = (result.ip, result.port)
        if key not in seen:
            seen.add(key)
            unique_results.append(result)
    
    return unique_results


def discover_servers_multi_interface(config: ClientConfig) -> List[DiscoveryResult]:
    """
    Perform UDP discovery using multiple network interfaces.
    
    This function:
    1. Selects interfaces based on config (whitelist/blacklist)
    2. Sends discovery messages to each interface's broadcast address
    3. Receives responses from all interfaces on a single socket
    4. Deduplicates results by (ip, port)
    
    Args:
        config: ClientConfig with discovery settings and interface filters
    
    Returns:
        List of unique DiscoveryResult objects for discovered servers.
        Returns empty list if no servers respond or timeout occurs.
    
    Raises:
        OSError: If socket operations fail
        ImportError: If network interface libraries are not available
    
    Example:
        >>> from discovery_client import ClientConfig
        >>> config = ClientConfig(timeout=5.0)
        >>> servers = discover_servers_multi_interface(config)
        >>> for server in servers:
        ...     print(f"Found: {server.ip}:{server.port}")
    """
    logger.info("Starting multi-interface discovery")
    
    # Track segmented network info for later use
    segmented_info = None
    
    # Select interfaces based on config
    try:
        interfaces = select_interfaces(config)
        logger.info(f"Selected {len(interfaces)} interface(s) for discovery")
        if logger.isEnabledFor(logging.DEBUG):
            for iface in interfaces:
                logger.debug(f"  - {iface.name}: {iface.ip}/{iface.netmask}")
        
        # Detect segmented networks - we'll check after discovery to see if warning is needed
        # Store the info but don't warn yet - we'll warn only if no servers are found
        segmented_info = detect_segmented_network(interfaces)
        if segmented_info:
            logger.info(
                "Network topology note: possible segmented corporate network detected "
                f"({segmented_info['network']}, ~{segmented_info['segments']} segments). "
                "UDP broadcast discovery typically only reaches the local broadcast domain "
                f"(likely {segmented_info['likely_broadcast_domain']})."
            )
    except ImportError as e:
        logger.error(
            f"Failed to enumerate network interfaces: {e}. "
            "Install netifaces or ifaddr: pip install django-udp-discovery-client[network]",
            exc_info=True
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error during interface selection: {e}", exc_info=True)
        raise
    
    if not interfaces:
        # No interfaces selected, return empty list
        logger.warning("No network interfaces selected for discovery")
        return []
    
    sock = None
    try:
        # Create a single socket for receiving responses from all interfaces
        sock = create_discovery_socket(config.timeout)
        
        # Send discovery request to each interface's broadcast address
        successful_sends = 0
        for iface in interfaces:
            try:
                # Get broadcast address for this interface
                broadcast_addr = get_interface_broadcast(iface)
                
                # Send discovery request to this interface's broadcast
                send_discovery_request(
                    sock,
                    config.discovery_message,
                    config.discovery_port,
                    broadcast_addr
                )
                successful_sends += 1
            except ValueError as e:
                # Skip this interface if broadcast cannot be computed
                logger.warning(
                    f"Skipping interface {iface.name}: failed to get broadcast address: {e}"
                )
                continue
            except OSError as e:
                # Skip this interface if send fails
                logger.warning(
                    f"Failed to send discovery request on interface {iface.name}: {e}"
                )
                continue
        
        if successful_sends == 0:
            logger.warning("No discovery requests were sent successfully")
            return []
        
        logger.info(f"Sent discovery requests on {successful_sends} interface(s)")
        
        # Receive responses from all interfaces
        results = receive_responses(sock, config)
        
        # Deduplicate results by (ip, port)
        unique_results = deduplicate_results(results)
        if len(unique_results) < len(results):
            logger.debug(
                f"Deduplicated {len(results)} responses to {len(unique_results)} unique servers"
            )
        
        # Segmented network warning is printed once by the caller (management command or
        # sanity_check) when results are empty; we only log at debug here to avoid duplication.
        if segmented_info and not unique_results:
            logger.debug(
                "Segmented network detected and no servers found; caller will print diagnostic."
            )
        elif segmented_info and unique_results:
            # Servers were found on segmented network - just log info, no warning
            logger.debug(
                f"Segmented network detected, but {len(unique_results)} server(s) found. "
                "Servers are on the same network segment as your client."
            )
        
        return unique_results
        
    except OSError as e:
        logger.error(f"Network error during multi-interface discovery: {e}", exc_info=True)
        raise
    finally:
        # Clean up socket
        if sock is not None:
            try:
                sock.close()
                logger.debug("Discovery socket closed")
            except OSError as e:
                logger.warning(f"Error closing socket: {e}")
