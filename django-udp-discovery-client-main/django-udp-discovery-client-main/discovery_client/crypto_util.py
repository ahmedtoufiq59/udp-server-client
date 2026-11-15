"""
Fernet helpers for encrypted UDP discovery (client).

Does not log secrets or decrypted payloads. Used when ``ClientConfig.encryption_enabled``
is True.
"""
from __future__ import annotations

import hmac
import secrets
import time
from typing import Optional, Tuple, Union

# pyrefly: ignore [missing-import]
from cryptography.fernet import Fernet, InvalidToken

#: Default maximum age in seconds of an accepted response token.
DEFAULT_TOKEN_TTL: float = 30.0

#: Default tolerance in seconds for clock differences between client and server.
DEFAULT_CLOCK_SKEW: float = 10.0

#: Separator between the discovery message (or response) and the nonce.
NONCE_SEPARATOR: bytes = b"|"


def validate_fernet_key(key_material: Union[str, bytes]) -> bytes:
    """
    Validate key material and return bytes suitable for ``Fernet``.

    Raises:
        TypeError: If ``key_material`` is not ``str`` or ``bytes``.
        ValueError: If empty or not a valid Fernet key.
    """
    if isinstance(key_material, str):
        key_bytes = key_material.strip().encode("ascii")
    elif isinstance(key_material, bytes):
        key_bytes = key_material.strip()
    else:
        raise TypeError(
            f"key_material must be str or bytes, got {type(key_material).__name__}"
        )
    if not key_bytes:
        raise ValueError("Fernet key must be non-empty.")
    try:
        Fernet(key_bytes)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid Fernet key format.") from exc
    return key_bytes


def build_fernet(secret: Union[str, bytes]) -> Fernet:
    """Construct ``Fernet`` from validated key material."""
    return Fernet(validate_fernet_key(secret))


def encrypt_payload(plaintext: bytes, fernet: Fernet) -> bytes:
    """Encrypt plaintext bytes."""
    return fernet.encrypt(plaintext)


def decrypt_payload(
    token: bytes,
    fernet: Fernet,
    ttl: Optional[float] = DEFAULT_TOKEN_TTL,
    clock_skew: float = DEFAULT_CLOCK_SKEW,
    now: Optional[float] = None,
) -> Optional[bytes]:
    """
    Decrypt a Fernet token, enforcing a maximum token age.

    Tokens up to ``ttl + clock_skew`` seconds old, or stamped up to ``clock_skew``
    seconds in the future, are accepted. ``ttl=None`` disables the age check (the
    signature is still verified). ``now`` overrides the current Unix time (tests).

    Returns ``None`` if the token is invalid, tampered with, expired, or from the future.
    """
    try:
        if ttl is not None:
            # extract_timestamp verifies the HMAC before trusting the timestamp.
            issued_at = fernet.extract_timestamp(token)
            current = time.time() if now is None else now
            if current - issued_at > ttl + clock_skew:
                return None
            if issued_at - current > clock_skew:
                return None
        return fernet.decrypt(token)
    except (InvalidToken, TypeError, ValueError):
        return None


def new_nonce() -> bytes:
    """Return a fresh random request nonce (32 lowercase hex characters)."""
    return secrets.token_hex(16).encode("ascii")


def build_request_plaintext(discovery_message: bytes, nonce: bytes) -> bytes:
    """Plaintext of an encrypted discovery request: ``<message>|<nonce>``."""
    return discovery_message + NONCE_SEPARATOR + nonce


def split_response_nonce(payload: bytes) -> Tuple[bytes, Optional[bytes]]:
    """
    Split ``<response>|<nonce>`` into ``(response, nonce)``.

    Returns ``(payload, None)`` when no separator is present.
    """
    body, sep, nonce = payload.rpartition(NONCE_SEPARATOR)
    if not sep:
        return payload, None
    return body, nonce


def nonce_matches(received: Optional[bytes], expected: bytes) -> bool:
    """Constant-time comparison of a received nonce against the one we sent."""
    if received is None:
        return False
    return hmac.compare_digest(received, expected)
