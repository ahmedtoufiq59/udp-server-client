"""
Network interface enumeration for discovery_client.

Enumerates active IPv4 non-loopback interfaces (IP, netmask, broadcast),
via netifaces or ifaddr. Provides InterfaceInfo and select_interfaces()
for whitelist/blacklist filtering. Required for multi-interface discovery.
"""
import ipaddress
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

# Import ClientConfig for type hints (avoid circular import)
if TYPE_CHECKING:
    from discovery_client.config import ClientConfig

# Try to import netifaces, fallback to ifaddr
try:
    import netifaces
    HAS_NETIFACES = True
except ImportError:
    HAS_NETIFACES = False

try:
    import ifaddr
    HAS_IFADDR = True
except ImportError:
    HAS_IFADDR = False

if not HAS_NETIFACES and not HAS_IFADDR:
    raise ImportError(
        "Either 'netifaces' or 'ifaddr' package is required. "
        "Install with: pip install django-udp-discovery-client[network]"
    )


@dataclass
class InterfaceInfo:
    """
    Information about a network interface.
    
    Attributes:
        name: Interface name (e.g., 'eth0', 'en0', 'Ethernet')
        ip: IPv4 address as string (e.g., '192.168.1.100')
        netmask: Netmask as string (e.g., '255.255.255.0')
        broadcast: Broadcast address as string, or None if not available
    """
    name: str
    ip: str
    netmask: str
    broadcast: Optional[str] = None


def _compute_broadcast(ip: str, netmask: str) -> str:
    """
    Compute broadcast address from IP and netmask.
    
    Args:
        ip: IPv4 address as string
        netmask: Netmask as string
        
    Returns:
        Broadcast address as string
    """
    try:
        # Create network from IP and netmask
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network.broadcast_address)
    except (ValueError, ipaddress.AddressValueError) as e:
        raise ValueError(f"Invalid IP/netmask combination: {ip}/{netmask}") from e


def _is_loopback(ip: str) -> bool:
    """Check if IP address is a loopback address."""
    try:
        addr = ipaddress.IPv4Address(ip)
        return addr.is_loopback
    except (ValueError, ipaddress.AddressValueError):
        return False


def _normalize_netmask(netmask: str) -> str:
    """
    Normalize netmask to standard dotted decimal format.
    
    Handles both CIDR notation (e.g., '/24') and dotted decimal (e.g., '255.255.255.0').
    """
    # If it's already in dotted decimal format, return as-is
    try:
        parts = netmask.split('.')
        if len(parts) == 4:
            # Validate it's a valid netmask
            ipaddress.IPv4Address(netmask)
            return netmask
    except (ValueError, AttributeError):
        pass
    
    # Try to parse as CIDR prefix length (with or without leading '/')
    netmask_str = str(netmask).strip()
    if netmask_str.startswith('/'):
        netmask_str = netmask_str[1:]
    
    try:
        prefix_len = int(netmask_str)
        if 0 <= prefix_len <= 32:
            # Convert prefix length to netmask
            mask_int = (0xFFFFFFFF >> (32 - prefix_len)) << (32 - prefix_len)
            return str(ipaddress.IPv4Address(mask_int))
    except (ValueError, AttributeError):
        pass
    
    # If we can't parse it, return as-is and let validation catch it
    return netmask


def _get_interfaces_netifaces() -> List[InterfaceInfo]:
    """Get interfaces using netifaces library."""
    interfaces = []
    
    for interface_name in netifaces.interfaces():
        # Get address info for this interface
        addrs = netifaces.ifaddresses(interface_name)
        
        # Look for IPv4 addresses (AF_INET = 2)
        if netifaces.AF_INET not in addrs:
            continue
        
        for addr_info in addrs[netifaces.AF_INET]:
            ip = addr_info.get('addr')
            netmask = addr_info.get('netmask')
            broadcast = addr_info.get('broadcast')
            
            if not ip or not netmask:
                continue
            
            # Skip loopback interfaces
            if _is_loopback(ip):
                continue
            
            # Normalize netmask
            netmask = _normalize_netmask(netmask)
            
            # Compute broadcast if missing
            if not broadcast:
                try:
                    broadcast = _compute_broadcast(ip, netmask)
                except ValueError:
                    # Skip interfaces with invalid IP/netmask
                    continue
            
            interfaces.append(InterfaceInfo(
                name=interface_name,
                ip=ip,
                netmask=netmask,
                broadcast=broadcast
            ))
    
    return interfaces


def _get_interfaces_ifaddr() -> List[InterfaceInfo]:
    """Get interfaces using ifaddr library (fallback)."""
    interfaces = []
    
    adapters = ifaddr.get_adapters()
    
    for adapter in adapters:
        for ip in adapter.ips:
            # Only process IPv4 addresses
            if ip.is_IPv4:
                ip_str = ip.ip
                netmask_str = ip.network_prefix
                
                # Skip loopback interfaces
                if _is_loopback(ip_str):
                    continue
                
                # Convert prefix length to netmask if needed
                if isinstance(netmask_str, int):
                    mask_int = (0xFFFFFFFF >> (32 - netmask_str)) << (32 - netmask_str)
                    netmask_str = str(ipaddress.IPv4Address(mask_int))
                else:
                    netmask_str = _normalize_netmask(str(netmask_str))
                
                # Compute broadcast address
                try:
                    broadcast = _compute_broadcast(ip_str, netmask_str)
                except ValueError:
                    # Skip interfaces with invalid IP/netmask
                    continue
                
                interfaces.append(InterfaceInfo(
                    name=adapter.nice_name or adapter.name,
                    ip=ip_str,
                    netmask=netmask_str,
                    broadcast=broadcast
                ))
    
    return interfaces


def get_interfaces() -> List[InterfaceInfo]:
    """
    Enumerate all active IPv4 network interfaces.
    
    Returns a list of InterfaceInfo objects for each active non-loopback
    interface. Broadcast addresses are computed if not provided by the system.
    
    Returns:
        List of InterfaceInfo objects
        
    Raises:
        ImportError: If neither netifaces nor ifaddr is available
        
    Example:
        >>> interfaces = get_interfaces()
        >>> for iface in interfaces:
        ...     print(f"{iface.name}: {iface.ip}/{iface.netmask} -> {iface.broadcast}")
    """
    if HAS_NETIFACES:
        return _get_interfaces_netifaces()
    elif HAS_IFADDR:
        return _get_interfaces_ifaddr()
    else:
        raise ImportError(
            "Neither netifaces nor ifaddr is available. "
            "Install with: pip install django-udp-discovery-client[network]"
        )


def select_interfaces(config: 'ClientConfig') -> List[InterfaceInfo]:
    """
    Select and filter network interfaces based on ClientConfig whitelist/blacklist.
    
    Filters the list of available network interfaces according to the whitelist
    and blacklist settings in the provided ClientConfig.
    
    Filtering rules:
    1. Start with all non-loopback interfaces from get_interfaces()
    2. If whitelist is set, keep only interfaces whose name is in the whitelist
    3. If blacklist is set, remove interfaces whose name is in the blacklist
    4. If both whitelist and blacklist are set, whitelist is applied first, then blacklist
    
    Interface name matching is case-sensitive and exact (e.g., "eth0" != "Eth0").
    
    Args:
        config: ClientConfig instance containing interfaces_whitelist and/or
                interfaces_blacklist settings
    
    Returns:
        List of InterfaceInfo objects that pass the filtering criteria.
        Returns empty list if no interfaces match the criteria.
    
    Raises:
        ImportError: If neither netifaces nor ifaddr is available (from get_interfaces)
    
    Example:
        >>> from discovery_client import ClientConfig, load_config
        >>> from discovery_client.network.interfaces import select_interfaces
        >>> 
        >>> # Whitelist only specific interfaces
        >>> config = ClientConfig(interfaces_whitelist=["eth0", "wlan0"])
        >>> interfaces = select_interfaces(config)
        >>> 
        >>> # Blacklist specific interfaces
        >>> config = ClientConfig(interfaces_blacklist=["lo", "docker0"])
        >>> interfaces = select_interfaces(config)
        >>> 
        >>> # Both whitelist and blacklist
        >>> config = ClientConfig(
        ...     interfaces_whitelist=["eth0", "eth1", "wlan0"],
        ...     interfaces_blacklist=["eth1"]
        ... )
        >>> interfaces = select_interfaces(config)
        >>> # Result: only eth0 and wlan0 (eth1 is blacklisted even though whitelisted)
    """
    # Get all available interfaces
    all_interfaces = get_interfaces()
    
    # Apply whitelist if set
    if config.interfaces_whitelist is not None:
        whitelist_set = set(config.interfaces_whitelist)
        filtered = [iface for iface in all_interfaces if iface.name in whitelist_set]
    else:
        filtered = all_interfaces
    
    # Apply blacklist if set
    if config.interfaces_blacklist is not None:
        blacklist_set = set(config.interfaces_blacklist)
        filtered = [iface for iface in filtered if iface.name not in blacklist_set]
    
    return filtered

