"""
Fernet utilities for optional UDP discovery encryption.

Resolves ``DISCOVERY_SECRET_KEY`` from Django project settings when that
attribute exists; otherwise from the ``DISCOVERY_SECRET_KEY`` environment
variable. Secret values are never logged.

When ``DISCOVERY_ENCRYPTION_ENABLED`` is True, the UDP listener uses these helpers
for wire encryption; otherwise they are optional for callers or tests.

Key rotation:
    ``DISCOVERY_PREVIOUS_SECRET_KEYS`` (settings list/tuple, or a comma-separated
    string in settings or the environment) lists older keys that are still accepted
    for decryption. Outgoing packets are always encrypted with ``DISCOVERY_SECRET_KEY``.
    To rotate with no downtime:

        1. Add the new key to every node's previous-keys list (still sending with the old).
        2. Make the new key ``DISCOVERY_SECRET_KEY`` everywhere and move the old one to
           the previous-keys list. Mixed nodes keep interoperating during the rollout.
        3. Once every node has the new key as current, remove the old one.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import threading
import time
from collections import OrderedDict
from typing import List, Optional, Sequence, Tuple, Union

# pyrefly: ignore [missing-import]
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

#: A single key or a rotation keyring; both expose encrypt/decrypt/extract_timestamp.
FernetLike = Union[Fernet, MultiFernet]
# pyrefly: ignore [missing-import]
from django.conf import settings as django_settings

#: Default maximum token age in seconds for encrypted discovery packets.
DEFAULT_TOKEN_TTL: float = 30.0

#: Default tolerance in seconds for clock differences between client and server.
DEFAULT_CLOCK_SKEW: float = 10.0

#: Separator between the discovery message (or response) and the client nonce.
NONCE_SEPARATOR: bytes = b"|"

_NONCE_RE = re.compile(rb"^[0-9a-f]{16,128}$")


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


def encrypt_bytes(plaintext: bytes, fernet: FernetLike) -> bytes:
    """Encrypt plaintext bytes."""
    return fernet.encrypt(plaintext)


def decrypt_bytes(
    token: bytes,
    fernet: FernetLike,
    ttl: Optional[float] = DEFAULT_TOKEN_TTL,
    clock_skew: float = DEFAULT_CLOCK_SKEW,
    now: Optional[float] = None,
) -> Optional[bytes]:
    """
    Decrypt a Fernet token, enforcing a maximum token age.

    Args:
        token: Fernet token bytes.
        fernet: ``Fernet`` for one key, or ``MultiFernet`` to accept any key in a
            rotation keyring.
        ttl: Maximum token age in seconds. ``None`` disables the age check
            (signature is still verified).
        clock_skew: Seconds of clock difference tolerated in both directions:
            tokens up to ``ttl + clock_skew`` seconds old are accepted, and tokens
            stamped up to ``clock_skew`` seconds in the future are accepted.
        now: Current Unix time (for tests); defaults to ``time.time()``.

    Returns:
        Plaintext bytes on success, or ``None`` if the token is invalid, tampered
        with, expired, or stamped too far in the future.

    Note:
        Does not log decrypted content or the secret key.
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


def token_fingerprint(token: bytes) -> Optional[bytes]:
    """
    Return a stable SHA-256 fingerprint of a Fernet token's decoded bytes.

    Hashing the decoded bytes (not the base64 text) means re-encoded variants of
    the same token, such as one with stray characters appended that the base64
    decoder ignores, map to the same fingerprint.
    """
    try:
        raw = base64.urlsafe_b64decode(token)
    except (binascii.Error, ValueError, TypeError):
        return None
    return hashlib.sha256(raw).digest()


class ReplayCache:
    """
    Time-limited, size-bounded set of recently seen token fingerprints.

    Entries live for ``ttl`` seconds; a token presented again within that window
    is reported as a replay. Use a lifetime of at least ``token_ttl + 2 * clock_skew``
    so a token cannot outlive its cache entry while still passing the age check.
    Thread-safe.
    """

    def __init__(self, ttl: float, max_entries: int = 10000) -> None:
        if ttl <= 0:
            raise ValueError("ReplayCache ttl must be positive.")
        if max_entries <= 0:
            raise ValueError("ReplayCache max_entries must be positive.")
        self.ttl = float(ttl)
        self.max_entries = int(max_entries)
        self._entries: "OrderedDict[bytes, float]" = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _prune(self, now: float) -> None:
        while self._entries:
            key, expires = next(iter(self._entries.items()))
            if expires > now:
                break
            del self._entries[key]

    def check_and_add(self, fingerprint: bytes, now: Optional[float] = None) -> bool:
        """
        Record ``fingerprint`` and report whether it is new.

        Returns:
            True if the fingerprint was not seen within the window (and is now
            recorded); False if it is a replay.
        """
        current = time.monotonic() if now is None else now
        with self._lock:
            self._prune(current)
            if fingerprint in self._entries:
                return False
            if len(self._entries) >= self.max_entries:
                # Evict the oldest entry; entries share one lifetime, so insertion
                # order is expiry order.
                self._entries.popitem(last=False)
            self._entries[fingerprint] = current + self.ttl
            return True


def parse_discovery_request(
    plaintext: bytes, discovery_message: bytes
) -> Tuple[bool, Optional[bytes]]:
    """
    Parse a decrypted discovery request.

    Accepted forms:
        * ``DISCOVERY_MESSAGE`` (no nonce; older encrypted clients)
        * ``DISCOVERY_MESSAGE|<nonce>`` where nonce is 16-128 lowercase hex chars

    Returns:
        ``(True, nonce_or_None)`` for a valid request, ``(False, None)`` otherwise.
    """
    if plaintext == discovery_message:
        return True, None
    head = discovery_message + NONCE_SEPARATOR
    if plaintext.startswith(head):
        nonce = plaintext[len(head):]
        if _NONCE_RE.match(nonce):
            return True, nonce
    return False, None


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


def _split_key_list(raw: Union[str, bytes, Sequence[Union[str, bytes]], None]) -> List[str]:
    """Normalize a list/tuple or comma-separated string of keys; drop blanks."""
    if raw is None:
        return []
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        items = [i.decode("utf-8") if isinstance(i, bytes) else str(i) for i in raw]
    else:
        raise TypeError(
            "DISCOVERY_PREVIOUS_SECRET_KEYS must be a list, tuple or comma-separated string"
        )
    return [i.strip() for i in items if i and i.strip()]


def resolve_previous_secret_keys() -> List[str]:
    """
    Return older keys still accepted for decryption, oldest-last as configured.

    Resolution order mirrors :func:`resolve_discovery_secret_key_string`:
    ``settings.DISCOVERY_PREVIOUS_SECRET_KEYS`` when that attribute exists, else the
    ``DISCOVERY_PREVIOUS_SECRET_KEYS`` environment variable (comma-separated).
    """
    if hasattr(django_settings, "DISCOVERY_PREVIOUS_SECRET_KEYS"):
        return _split_key_list(django_settings.DISCOVERY_PREVIOUS_SECRET_KEYS)
    return _split_key_list(os.environ.get("DISCOVERY_PREVIOUS_SECRET_KEYS"))


def build_keyring(
    current_key: Union[str, bytes],
    previous_keys: Sequence[Union[str, bytes]] = (),
) -> MultiFernet:
    """
    Build a ``MultiFernet`` that encrypts with ``current_key`` and decrypts with
    ``current_key`` or any of ``previous_keys``. Duplicates are dropped.

    Raises:
        ValueError / TypeError: If any key is not valid Fernet material.
    """
    ordered: List[bytes] = []
    for material in (current_key, *previous_keys):
        key_bytes = validate_fernet_key(material)
        if key_bytes not in ordered:
            ordered.append(key_bytes)
    return MultiFernet([Fernet(k) for k in ordered])


def build_keyring_from_settings() -> Optional[MultiFernet]:
    """
    Build the rotation keyring from ``DISCOVERY_SECRET_KEY`` and
    ``DISCOVERY_PREVIOUS_SECRET_KEYS``.

    Returns:
        ``MultiFernet`` when a current key is configured, else ``None``.

    Raises:
        ValueError: If any configured key is invalid, or previous keys are set
            without a current key.
    """
    current = resolve_discovery_secret_key_string()
    try:
        previous = resolve_previous_secret_keys()
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    if not current:
        if previous:
            raise ValueError(
                "DISCOVERY_PREVIOUS_SECRET_KEYS is set but DISCOVERY_SECRET_KEY is not."
            )
        return None
    try:
        return build_keyring(current, previous)
    except TypeError as exc:
        raise ValueError("Invalid Fernet key format.") from exc
