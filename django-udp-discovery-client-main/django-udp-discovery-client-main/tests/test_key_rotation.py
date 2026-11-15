"""Tests for client-side Fernet key rotation (current key + previous keys)."""
import socket
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from discovery_client import ClientConfig, load_config
from discovery_client.crypto_util import build_keyring, decrypt_payload, new_nonce
from discovery_client.network.socket import _outgoing_discovery_payload, receive_responses


@pytest.fixture
def old_key() -> str:
    return Fernet.generate_key().decode("ascii")


@pytest.fixture
def new_key() -> str:
    return Fernet.generate_key().decode("ascii")


def _sock(*packets):
    sock = MagicMock()
    sock.recvfrom.side_effect = [(p, ("10.0.0.1", 9999)) for p in packets] + [socket.timeout]
    return sock


class TestBuildKeyring:
    def test_encrypts_with_current_decrypts_with_any(self, old_key, new_key):
        ring = build_keyring(new_key, [old_key])
        token = ring.encrypt(b"x")
        assert Fernet(new_key.encode()).decrypt(token) == b"x"
        with pytest.raises(Exception):
            Fernet(old_key.encode()).decrypt(token)
        assert decrypt_payload(Fernet(old_key.encode()).encrypt(b"y"), ring) == b"y"

    def test_duplicates_dropped(self, new_key):
        ring = build_keyring(new_key, [new_key])
        assert decrypt_payload(ring.encrypt(b"x"), ring) == b"x"

    def test_invalid_previous_key_rejected(self, new_key):
        with pytest.raises(ValueError):
            build_keyring(new_key, ["not-a-key"])


class TestClientConfigRotation:
    def test_request_uses_current_key(self, old_key, new_key):
        cfg = ClientConfig(
            encryption_enabled=True, secret_key=new_key, previous_secret_keys=[old_key]
        )
        token = _outgoing_discovery_payload(cfg, new_nonce())
        Fernet(new_key.encode()).decrypt(token)
        with pytest.raises(Exception):
            Fernet(old_key.encode()).decrypt(token)

    def test_accepts_response_from_server_still_on_old_key(self, old_key, new_key):
        cfg = ClientConfig(
            encryption_enabled=True, secret_key=new_key, previous_secret_keys=[old_key]
        )
        nonce = new_nonce()
        reply = Fernet(old_key.encode()).encrypt(b"SERVER_IP:10.0.0.1|" + nonce)
        results = receive_responses(_sock(reply), cfg, expected_nonce=nonce)
        assert [r.ip for r in results] == ["10.0.0.1"]

    def test_rejects_response_after_old_key_removed(self, old_key, new_key):
        cfg = ClientConfig(encryption_enabled=True, secret_key=new_key)
        nonce = new_nonce()
        reply = Fernet(old_key.encode()).encrypt(b"SERVER_IP:10.0.0.1|" + nonce)
        assert receive_responses(_sock(reply), cfg, expected_nonce=nonce) == []

    def test_previous_keys_must_be_a_list(self, old_key, new_key):
        with pytest.raises(TypeError):
            ClientConfig(
                encryption_enabled=True, secret_key=new_key, previous_secret_keys=old_key
            )

    def test_invalid_previous_key(self, new_key):
        with pytest.raises(ValueError):
            ClientConfig(
                encryption_enabled=True, secret_key=new_key, previous_secret_keys=["bad"]
            )

    def test_keys_not_in_repr(self, old_key, new_key):
        cfg = ClientConfig(
            encryption_enabled=True, secret_key=new_key, previous_secret_keys=[old_key]
        )
        text = repr(cfg)
        assert new_key not in text
        assert old_key not in text

    def test_previous_keys_from_env(self, monkeypatch, old_key, new_key):
        other = Fernet.generate_key().decode("ascii")
        monkeypatch.setenv("DISCOVERY_CLIENT_SECRET_KEY", new_key)
        monkeypatch.setenv("DISCOVERY_CLIENT_PREVIOUS_SECRET_KEYS", f"{old_key}, {other}")
        cfg = load_config(encryption_enabled=True)
        assert cfg.previous_secret_keys == [old_key, other]

    def test_previous_keys_from_server_named_env(self, monkeypatch, old_key, new_key):
        monkeypatch.delenv("DISCOVERY_CLIENT_PREVIOUS_SECRET_KEYS", raising=False)
        monkeypatch.setenv("DISCOVERY_CLIENT_SECRET_KEY", new_key)
        monkeypatch.setenv("DISCOVERY_PREVIOUS_SECRET_KEYS", old_key)
        cfg = load_config(encryption_enabled=True)
        assert cfg.previous_secret_keys == [old_key]
