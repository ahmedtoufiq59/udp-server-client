"""
Discovery result data structures.

Defines DiscoveryResult, the type returned by discover() and discover_one().
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class DiscoveryResult:
    """
    A single discovered server returned by discover() or discover_one().

    Attributes:
        ip: IPv4 address of the server (e.g. "192.168.1.100").
        port: Port number (1-65535).
        raw_response: Raw bytes of the server response (e.g. b"SERVER_IP:192.168.1.100:8000").
        extra: Optional metadata dict (e.g. source_address); default None.

    Example:
        >>> r = DiscoveryResult(ip="192.168.1.100", port=8000, raw_response=b"SERVER_IP:...")
        >>> print(r.ip, r.port)
    """
    ip: str
    port: int
    raw_response: bytes
    extra: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate result fields."""
        # Validate IP format (basic check)
        if not self.ip or not isinstance(self.ip, str):
            raise ValueError(f"ip must be a non-empty string, got {type(self.ip).__name__}")
        
        # Validate port range
        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ValueError(f"port must be an integer between 1 and 65535, got {self.port}")
        
        # Validate raw_response
        if not isinstance(self.raw_response, bytes):
            raise ValueError(f"raw_response must be bytes, got {type(self.raw_response).__name__}")
        
        # Validate extra if provided
        if self.extra is not None and not isinstance(self.extra, dict):
            raise ValueError(f"extra must be a dict or None, got {type(self.extra).__name__}")
