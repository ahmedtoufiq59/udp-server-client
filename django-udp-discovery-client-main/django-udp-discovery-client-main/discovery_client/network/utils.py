"""
Network utility functions for netmask and network calculations.

Provides helpers for netmask-to-prefix conversion, computing network ranges,
and calculating broadcast addresses.
"""
import ipaddress
from typing import Union


def netmask_to_prefix(netmask: str) -> int:
    """
    Convert netmask to CIDR prefix length.
    
    Converts a netmask in dotted decimal notation (e.g., "255.255.255.0")
    to a CIDR prefix length (e.g., 24).
    
    Args:
        netmask: Netmask as string in dotted decimal format (e.g., "255.255.255.0")
        
    Returns:
        CIDR prefix length as integer (0-32)
        
    Raises:
        ValueError: If netmask is invalid or non-contiguous
        
    Example:
        >>> netmask_to_prefix("255.255.255.0")
        24
        >>> netmask_to_prefix("255.0.0.0")
        8
    """
    try:
        # Parse as IPv4Address to validate format
        mask_addr = ipaddress.IPv4Address(netmask)
        mask_int = int(mask_addr)
        
        # Validate it's a valid contiguous netmask
        # A valid netmask must be a sequence of 1s followed by 0s
        # We can check this by inverting and checking if (inverted + 1) is a power of 2
        inverted = (~mask_int) & 0xFFFFFFFF
        if inverted == 0:
            # All 1s - /32
            return 32
        
        # Check if inverted + 1 is a power of 2
        # For a valid netmask: inverted = 0...01...1, so inverted + 1 = 0...10...0 (power of 2)
        inverted_plus_one = inverted + 1
        if (inverted_plus_one & (inverted_plus_one - 1)) != 0:
            raise ValueError(f"Non-contiguous netmask: {netmask}")
        
        # Count leading 1s by finding the position of the first 0
        # The prefix length is 32 - number of trailing 0s in inverted
        # Which equals 32 - log2(inverted_plus_one)
        # Or we can count bits directly
        prefix = 0
        for i in range(32):
            if mask_int & (1 << (31 - i)):
                prefix += 1
            else:
                break
        
        return prefix
        
    except (ValueError, ipaddress.AddressValueError) as e:
        if "Non-contiguous" in str(e):
            raise
        raise ValueError(f"Invalid netmask format: {netmask}") from e


def prefix_to_netmask(prefix: int) -> str:
    """
    Convert CIDR prefix length to netmask.
    
    Converts a CIDR prefix length (e.g., 24) to a netmask in dotted decimal
    notation (e.g., "255.255.255.0").
    
    Args:
        prefix: CIDR prefix length (0-32)
        
    Returns:
        Netmask as string in dotted decimal format
        
    Raises:
        ValueError: If prefix is out of valid range (0-32)
        
    Example:
        >>> prefix_to_netmask(24)
        '255.255.255.0'
        >>> prefix_to_netmask(8)
        '255.0.0.0'
    """
    if not (0 <= prefix <= 32):
        raise ValueError(f"Prefix length must be between 0 and 32, got {prefix}")
    
    # Calculate netmask: (2^prefix - 1) << (32 - prefix)
    # For prefix=24: (2^24 - 1) << 8 = 0xFFFFFF00 = 255.255.255.0
    if prefix == 0:
        mask_int = 0
    elif prefix == 32:
        mask_int = 0xFFFFFFFF
    else:
        mask_int = ((1 << prefix) - 1) << (32 - prefix)
    
    return str(ipaddress.IPv4Address(mask_int))


def network_from_ip_and_mask(ip: str, mask: Union[str, int]) -> ipaddress.IPv4Network:
    """
    Create IPv4Network object from IP address and netmask.
    
    Args:
        ip: IPv4 address as string (e.g., "192.168.1.100")
        mask: Netmask as string (e.g., "255.255.255.0") or prefix length as int (e.g., 24)
        
    Returns:
        IPv4Network object representing the network
        
    Raises:
        ValueError: If IP or mask is invalid
        
    Example:
        >>> network = network_from_ip_and_mask("192.168.1.100", "255.255.255.0")
        >>> str(network)
        '192.168.1.0/24'
        >>> network = network_from_ip_and_mask("10.0.0.1", 8)
        >>> str(network)
        '10.0.0.0/8'
    """
    try:
        # Normalize mask to prefix length if it's a string
        if isinstance(mask, str):
            # Check if it's already a prefix notation like "/24"
            if mask.startswith('/'):
                prefix = int(mask[1:])
            else:
                # Convert netmask to prefix
                prefix = netmask_to_prefix(mask)
        elif isinstance(mask, int):
            prefix = mask
        else:
            raise TypeError(f"Mask must be str or int, got {type(mask).__name__}")
        
        # Validate prefix range
        if not (0 <= prefix <= 32):
            raise ValueError(f"Prefix length must be between 0 and 32, got {prefix}")
        
        # Create network object
        network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
        return network
        
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        raise ValueError(f"Invalid IP/mask combination: {ip}/{mask}") from e


def broadcast_from_ip_and_mask(ip: str, mask: Union[str, int]) -> str:
    """
    Calculate broadcast address from IP address and netmask.
    
    Args:
        ip: IPv4 address as string (e.g., "192.168.1.100")
        mask: Netmask as string (e.g., "255.255.255.0") or prefix length as int (e.g., 24)
        
    Returns:
        Broadcast address as string
        
    Raises:
        ValueError: If IP or mask is invalid
        
    Example:
        >>> broadcast_from_ip_and_mask("192.168.1.100", "255.255.255.0")
        '192.168.1.255'
        >>> broadcast_from_ip_and_mask("10.0.0.1", 8)
        '10.255.255.255'
    """
    network = network_from_ip_and_mask(ip, mask)
    return str(network.broadcast_address)
