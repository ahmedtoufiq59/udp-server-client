"""
Fernet helpers for encrypted UDP discovery (client).

Does not log secrets or decrypted payloads. Used when ``ClientConfig.encryption_enabled``
is True.
"""
from __future__ import annotations

from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken


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


def decrypt_payload(token: bytes, fernet: Fernet) -> Optional[bytes]:
    """
    Decrypt a Fernet token.

    Returns ``None`` on :class:`~cryptography.fernet.InvalidToken`` (invalid or expired).
    """
    try:
        return fernet.decrypt(token)
    except InvalidToken:
        return None
