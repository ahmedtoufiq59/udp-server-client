"""
Configuration module for UDP discovery client.

Provides ClientConfig dataclass with defaults, runtime overrides, and
environment variable support.
"""
import os
from dataclasses import dataclass, field
from typing import Optional, List, Union, Any


def _normalize_to_bytes(value: Union[str, bytes]) -> bytes:
    """Convert string or bytes to bytes."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode('utf-8')
    raise TypeError(f"Expected str or bytes, got {type(value).__name__}")


def _parse_bool(value: str) -> bool:
    """Parse boolean from environment variable string."""
    return value.lower() in ('true', '1', 'yes', 'on')


def _parse_list(value: str) -> List[str]:
    """Parse comma-separated list from environment variable string."""
    if not value.strip():
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


@dataclass
class ClientConfig:
    """
    Configuration for UDP discovery client.

    Supports built-in defaults, environment variables (DISCOVERY_CLIENT_*), and
    runtime overrides. When using load_config() or from_env(), priority is:
    defaults < env vars < keyword overrides.

    Attributes:
        discovery_port: UDP port for discovery (default: 9999).
        discovery_message: Message to send for discovery (default: b"DISCOVER_SERVER").
        response_prefix: Expected prefix in server responses (default: b"SERVER_IP:").
        timeout: Timeout in seconds for discovery operations (default: 5.0).
        retries: Number of retry attempts (default: 3). Reserved for future use.
        enable_subnet_scan: Whether to enable subnet scan (default: True). Reserved for future use.
        interfaces_whitelist: If set, only these interface names are used (default: None).
        interfaces_blacklist: If set, these interface names are excluded (default: None).
        encryption_enabled: When True, discovery requests and responses use Fernet
            (must match server ``DISCOVERY_ENCRYPTION_ENABLED``). Default: False.
        secret_key: Fernet key (``Fernet.generate_key()`` string). Required when
            ``encryption_enabled`` is True. Env: ``DISCOVERY_CLIENT_SECRET_KEY`` or
            ``DISCOVERY_SECRET_KEY`` (fallback for parity with server env).
    """
    discovery_port: int = 9999
    discovery_message: bytes = field(default_factory=lambda: b"DISCOVER_SERVER")
    response_prefix: bytes = field(default_factory=lambda: b"SERVER_IP:")
    timeout: float = 5.0
    retries: int = 3
    enable_subnet_scan: bool = True
    interfaces_whitelist: Optional[List[str]] = None
    interfaces_blacklist: Optional[List[str]] = None
    encryption_enabled: bool = False
    secret_key: Optional[str] = None
    _fernet: Any = field(init=False, repr=False, compare=False, default=None)
    
    def __post_init__(self):
        """Validate and normalize configuration values."""
        # Validate port range
        if not (1 <= self.discovery_port <= 65535):
            raise ValueError(
                f"discovery_port must be between 1 and 65535, got {self.discovery_port}"
            )
        
        # Normalize message and prefix to bytes
        if isinstance(self.discovery_message, (str, bytes)):
            self.discovery_message = _normalize_to_bytes(self.discovery_message)
        else:
            raise TypeError(
                f"discovery_message must be str or bytes, got {type(self.discovery_message).__name__}"
            )
        
        if isinstance(self.response_prefix, (str, bytes)):
            self.response_prefix = _normalize_to_bytes(self.response_prefix)
        else:
            raise TypeError(
                f"response_prefix must be str or bytes, got {type(self.response_prefix).__name__}"
            )
        
        # Validate timeout
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
        
        # Validate retries
        if self.retries < 0:
            raise ValueError(f"retries must be non-negative, got {self.retries}")

        if self.encryption_enabled:
            if not (self.secret_key and str(self.secret_key).strip()):
                raise ValueError(
                    "encryption_enabled requires a non-empty secret_key "
                    "(DISCOVERY_CLIENT_SECRET_KEY / DISCOVERY_SECRET_KEY or secret_key=...)"
                )
            from discovery_client.crypto_util import build_fernet

            object.__setattr__(self, "_fernet", build_fernet(str(self.secret_key).strip()))
        else:
            object.__setattr__(self, "_fernet", None)
    
    @classmethod
    def from_env(cls, **overrides: object) -> 'ClientConfig':
        """
        Create ClientConfig from environment variables with optional overrides.

        Priority: built-in defaults < DISCOVERY_CLIENT_* env vars < **overrides.
        Only keys not present in overrides are read from the environment.

        Environment variables (all optional, prefix DISCOVERY_CLIENT_):
            PORT: Discovery port (int)
            MESSAGE: Discovery message (str/bytes)
            RESPONSE_PREFIX: Response prefix (str/bytes)
            TIMEOUT: Timeout in seconds (float)
            RETRIES: Number of retries (int)
            ENABLE_SUBNET_SCAN: Enable subnet scan (bool: true/1/yes/on)
            INTERFACES_WHITELIST: Comma-separated interface names
            INTERFACES_BLACKLIST: Comma-separated interface names
            ENCRYPTION_ENABLED: Fernet mode (bool). Reads ``DISCOVERY_CLIENT_ENCRYPTION_ENABLED``
            first, then ``DISCOVERY_ENCRYPTION_ENABLED`` (same name as server). Requires a secret key.
            SECRET_KEY: Fernet key (also reads DISCOVERY_SECRET_KEY if this is unset)

        Args:
            **overrides: Runtime overrides; take precedence over env vars and defaults.

        Returns:
            ClientConfig: New instance with merged configuration.
        """
        env_prefix = "DISCOVERY_CLIENT_"
        
        # Build config dict from environment variables
        config_dict = {}
        
        # Port
        if 'discovery_port' not in overrides:
            port_str = os.environ.get(f"{env_prefix}PORT")
            if port_str:
                try:
                    config_dict['discovery_port'] = int(port_str)
                except ValueError:
                    raise ValueError(f"Invalid port value: {port_str}")
        
        # Message
        if 'discovery_message' not in overrides:
            message = os.environ.get(f"{env_prefix}MESSAGE")
            if message:
                config_dict['discovery_message'] = message
        
        # Response prefix
        if 'response_prefix' not in overrides:
            prefix = os.environ.get(f"{env_prefix}RESPONSE_PREFIX")
            if prefix:
                config_dict['response_prefix'] = prefix
        
        # Timeout
        if 'timeout' not in overrides:
            timeout_str = os.environ.get(f"{env_prefix}TIMEOUT")
            if timeout_str:
                try:
                    config_dict['timeout'] = float(timeout_str)
                except ValueError:
                    raise ValueError(f"Invalid timeout value: {timeout_str}")
        
        # Retries
        if 'retries' not in overrides:
            retries_str = os.environ.get(f"{env_prefix}RETRIES")
            if retries_str:
                try:
                    config_dict['retries'] = int(retries_str)
                except ValueError:
                    raise ValueError(f"Invalid retries value: {retries_str}")
        
        # Enable subnet scan
        if 'enable_subnet_scan' not in overrides:
            subnet_scan = os.environ.get(f"{env_prefix}ENABLE_SUBNET_SCAN")
            if subnet_scan:
                config_dict['enable_subnet_scan'] = _parse_bool(subnet_scan)
        
        # Interfaces whitelist
        if 'interfaces_whitelist' not in overrides:
            whitelist = os.environ.get(f"{env_prefix}INTERFACES_WHITELIST")
            if whitelist:
                config_dict['interfaces_whitelist'] = _parse_list(whitelist)
        
        # Interfaces blacklist
        if 'interfaces_blacklist' not in overrides:
            blacklist = os.environ.get(f"{env_prefix}INTERFACES_BLACKLIST")
            if blacklist:
                config_dict['interfaces_blacklist'] = _parse_list(blacklist)

        # Encrypted discovery (Fernet)
        if 'encryption_enabled' not in overrides:
            enc = os.environ.get(f"{env_prefix}ENCRYPTION_ENABLED")
            if not enc:
                enc = os.environ.get("DISCOVERY_ENCRYPTION_ENABLED")
            if enc:
                config_dict['encryption_enabled'] = _parse_bool(enc)

        if 'secret_key' not in overrides:
            sk = os.environ.get(f"{env_prefix}SECRET_KEY")
            if not sk:
                sk = os.environ.get("DISCOVERY_SECRET_KEY")
            if sk:
                config_dict['secret_key'] = sk.strip()
        
        # Merge env vars with overrides (overrides take precedence)
        config_dict.update(overrides)
        
        return cls(**config_dict)


def load_config(**kwargs: object) -> ClientConfig:
    """
    Load and validate ClientConfig with optional overrides.

    Priority order (highest wins): (1) keyword arguments, (2) environment
    variables (DISCOVERY_CLIENT_*), (3) built-in defaults. So load_config()
    uses defaults plus any DISCOVERY_CLIENT_* env vars; load_config(timeout=5)
    uses 5 for timeout and env/defaults for the rest.

    Args:
        **kwargs: Optional keyword overrides (e.g. timeout=10.0, discovery_port=8888).
            These take precedence over environment variables and defaults.

    Returns:
        ClientConfig: Validated configuration instance.

    Example:
        >>> config = load_config(timeout=10.0, discovery_port=8888)
        >>> config = load_config()  # Uses defaults and env vars only
    """
    return ClientConfig.from_env(**kwargs)

