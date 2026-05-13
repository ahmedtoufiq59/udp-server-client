"""
Fernet utilities for optional UDP discovery encryption.

Resolves ``DISCOVERY_SECRET_KEY`` from Django project settings when that
attribute exists; otherwise from the ``DISCOVERY_SECRET_KEY`` environment
variable. Secret values are never logged.

When ``DISCOVERY_ENCRYPTION_ENABLED`` is True, the UDP listener uses these helpers
for wire encryption; otherwise they are optional for callers or tests.
"""
from __future__ import annotations

import os
from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings as django_settings


def resolve_discovery_secret_key_string() -> str:
    """
    Return the configured discovery secret as a stripped string, or "" if unset.

    Resolution order:
        1. ``django.conf.settings.DISCOVERY_SECRET_KEY`` when that attribute exists
           (``str`` or ``bytes``), after strip. If the attribute exists and is empty,
           the environment is not consulted.
        2. Otherwise ``os.environ.get("DISCOVERY_SECRET_KEY")``, stripped.

    Returns:
        Non-empty key material, or "" if no key is configured.

    Note:
        Does not log or raise; callers validate non-empty keys as needed.
    """
    if hasattr(django_settings, "DISCOVERY_SECRET_KEY"):
        raw = django_settings.DISCOVERY_SECRET_KEY
        if isinstance(raw, bytes):
            return raw.decode("utf-8").strip()
        return str(raw).strip()

    env = os.environ.get("DISCOVERY_SECRET_KEY")
    if env is None:
        return ""
    return env.strip()


def validate_fernet_key(key_material: Union[str, bytes]) -> bytes:
    """
    Validate key material and return bytes suitable for ``Fernet``.

    Args:
        key_material: URL-safe base64-encoded 32-byte key (typical ``Fernet`` key).

    Returns:
        Stripped key bytes accepted by ``cryptography.fernet.Fernet``.

    Raises:
        TypeError: If ``key_material`` is not ``str`` or ``bytes``.
        ValueError: If empty or not a valid Fernet key (message does not echo secrets).
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


def build_fernet(key_material: Union[str, bytes]) -> Fernet:
    """
    Construct a ``Fernet`` instance from validated key material.

    Raises:
        Same as :func:`validate_fernet_key`.
    """
    return Fernet(validate_fernet_key(key_material))


def encrypt_bytes(plaintext: bytes, fernet: Fernet) -> bytes:
    """Encrypt plaintext bytes."""
    return fernet.encrypt(plaintext)


def decrypt_bytes(token: bytes, fernet: Fernet) -> Optional[bytes]:
    """
    Decrypt a Fernet token.

    Returns:
        Plaintext bytes on success, or ``None`` on
        :class:`~cryptography.fernet.InvalidToken` (invalid or expired token).

    Note:
        Does not log decrypted content or the secret key.
    """
    try:
        return fernet.decrypt(token)
    except InvalidToken:
        return None


def get_validated_key_bytes_from_settings() -> Optional[bytes]:
    """
    Load the discovery secret from settings/env and validate as a Fernet key.

    Returns:
        Validated key bytes, or ``None`` if no key is configured.

    Raises:
        ValueError: If a key is configured but not valid Fernet material.
    """
    raw = resolve_discovery_secret_key_string()
    if not raw:
        return None
    return validate_fernet_key(raw)


def build_fernet_from_settings() -> Optional[Fernet]:
    """
    Build a ``Fernet`` from the configured discovery secret, if any.

    Returns:
        ``Fernet`` instance when a valid key is configured, else ``None``.

    Raises:
        ValueError: If a non-empty key is present but invalid.
    """
    key_bytes = get_validated_key_bytes_from_settings()
    if key_bytes is None:
        return None
    return Fernet(key_bytes)
