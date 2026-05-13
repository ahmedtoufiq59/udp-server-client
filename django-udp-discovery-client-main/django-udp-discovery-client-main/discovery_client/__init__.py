"""
UDP discovery client for django-udp-discovery servers.

Public API: discover(), discover_one(), ClientConfig, load_config(), DiscoveryResult.
Use discover() or discover_one() to find servers on the local network; configure
via ClientConfig or load_config() (env: DISCOVERY_CLIENT_*).
"""
__version__ = "1.0.0"

import logging
from discovery_client.config import ClientConfig, load_config
from discovery_client.results import DiscoveryResult
from discovery_client.network.socket import (
    discover_servers_single_broadcast,
    discover_servers_multi_interface,
)
from typing import List, Optional

# Module-level logger
logger = logging.getLogger("django_udp_discovery_client")

__all__ = [
    'ClientConfig',
    'load_config',
    'DiscoveryResult',
    'discover',
    'discover_one',
]


def discover(config: Optional[ClientConfig] = None) -> List[DiscoveryResult]:
    """
    Discover django-udp-discovery servers on the local network.

    Sends UDP discovery requests to the network and collects responses from
    servers that use the ``SERVER_IP:`` response prefix. Uses multi-interface
    broadcast; results are deduplicated by (ip, port). When
    ``ClientConfig.encryption_enabled`` is True, requests and responses are
    wrapped with Fernet (same key as server ``DISCOVERY_SECRET_KEY``).

    Args:
        config: Optional ClientConfig. If None, uses load_config() (defaults + env).

    Returns:
        List[DiscoveryResult]: One entry per discovered server (ip, port, raw_response, extra).
        Empty list if no servers are found, timeout, or on network/import errors (logged).

    Example:
        >>> from discovery_client import discover, load_config
        >>> servers = discover()
        >>> for s in servers:
        ...     print(s.ip, s.port)  # DiscoveryResult attributes
        >>> servers = discover(config=load_config(timeout=10.0))
    """
    if config is None:
        config = load_config()
    
    # Perform discovery using multi-interface broadcast
    try:
        logger.info("Starting server discovery")
        return discover_servers_multi_interface(config)
    except OSError as e:
        # Socket errors - return empty list
        logger.error(
            f"Network error during discovery: {e}. "
            "Discovery failed due to socket operation error.",
            exc_info=True
        )
        return []
    except ImportError as e:
        # Missing network libraries - return empty list
        logger.error(
            f"Missing network interface libraries: {e}. "
            "Install with: pip install django-udp-discovery-client[network]",
            exc_info=True
        )
        return []
    except Exception as e:
        # Unexpected errors - log and return empty list
        logger.error(
            f"Unexpected error during discovery: {e}",
            exc_info=True
        )
        return []


def discover_one(config: Optional[ClientConfig] = None) -> Optional[DiscoveryResult]:
    """
    Discover a single django-udp-discovery server (first respondent).

    Convenience wrapper around discover(): returns the first DiscoveryResult
    or None if no servers are found. Same protocol and config as discover().

    Args:
        config: Optional ClientConfig. If None, uses load_config() (defaults + env).

    Returns:
        Optional[DiscoveryResult]: First discovered server (ip, port, raw_response, extra),
        or None if none found or on error.

    Example:
        >>> from discovery_client import discover_one
        >>> server = discover_one()
        >>> if server:
        ...     print(server.ip, server.port)
    """
    if config is None:
        config = load_config()
    
    # Call discover() and return first result
    logger.debug("discover_one() called - will return first server or None")
    servers = discover(config=config)
    if servers:
        logger.debug(f"discover_one() found server: {servers[0].ip}:{servers[0].port}")
        return servers[0]
    logger.debug("discover_one() found no servers")
    return None

