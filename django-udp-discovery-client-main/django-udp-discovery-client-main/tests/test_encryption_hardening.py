"""
Tests for encrypted discovery hardening on the client: token TTL with clock-skew
tolerance, tamper detection, and request nonces echoed by the server.
"""
import base64
import os
import socket
import time
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from discovery_client import ClientConfig, load_config
from discovery_client.crypto_util import (
    DEFAULT_CLOCK_SKEW,
    DEFAULT_TOKEN_TTL,
    build_request_plaintext,
    decrypt_payload,
    new_nonce,
    nonce_matches,
    split_response_nonce,
)
from discovery_client.network.interfaces import InterfaceInfo
from discovery_client.network.socket import (
    discover_servers_multi_interface,
    receive_responses,
)


def _flip_bit(token: bytes, byte_index: int, bit: int = 0) -> bytes:
    raw = bytearray(base64.urlsafe_b64decode(token))
    raw[byte_index] ^= 1 << bit
    return base64.urlsafe_b64encode(bytes(raw))


@pytest.fixture
def key() -> str:
    return Fernet.generate_key().decode("ascii")


@pytest.fixture
def fernet(key: str) -> Fernet:
    return Fernet(key.encode("ascii"))


class TestDecryptPayloadTtl:
    def test_defaults(self):
        assert DEFAULT_TOKEN_TTL == 30.0
        assert DEFAULT_CLOCK_SKEW == 10.0

    def test_fresh_token_accepted(self, fernet):
        assert decrypt_payload(fernet.encrypt(b"hi"), fernet) == b"hi"

    def test_expired_token_rejected(self, fernet):
        now = time.time()
        token = fernet.encrypt_at_time(b"hi", int(now) - 120)
        assert decrypt_payload(token, fernet, ttl=30, clock_skew=10, now=now) is None

    def test_token_just_past_ttl_but_within_skew_accepted(self, fernet):
        now = 1_700_000_000
        token = fernet.encrypt_at_time(b"hi", now - 35)
        assert decrypt_payload(token, fernet, ttl=30, clock_skew=10, now=now) == b"hi"

    def test_token_past_ttl_plus_skew_rejected(self, fernet):
        now = 1_700_000_000
        token = fernet.encrypt_at_time(b"hi", now - 41)
        assert decrypt_payload(token, fernet, ttl=30, clock_skew=10, now=now) is None

    def test_future_token_within_skew_accepted(self, fernet):
        now = 1_700_000_000
        token = fernet.encrypt_at_time(b"hi", now + 8)
        assert decrypt_payload(token, fernet, ttl=30, clock_skew=10, now=now) == b"hi"

    def test_future_token_beyond_skew_rejected(self, fernet):
        now = 1_700_000_000
        token = fernet.encrypt_at_time(b"hi", now + 11)
        assert decrypt_payload(token, fernet, ttl=30, clock_skew=10, now=now) is None

    def test_ttl_none_disables_age_check(self, fernet):
        token = fernet.encrypt_at_time(b"hi", 1_000)
        assert decrypt_payload(token, fernet, ttl=None) == b"hi"


class TestDecryptPayloadTamper:
    @pytest.mark.parametrize("byte_index", [0, 1, 5, 9, 20, 40, -1])
    def test_bit_flipped_real_token_rejected(self, fernet, byte_index):
        token = fernet.encrypt(b"SERVER_IP:10.0.0.1|" + new_nonce())
        raw_len = len(base64.urlsafe_b64decode(token))
        tampered = _flip_bit(token, byte_index % raw_len)
        assert tampered != token
        assert decrypt_payload(tampered, fernet) is None
        assert decrypt_payload(tampered, fernet, ttl=None) is None

    def test_truncated_token_rejected(self, fernet):
        token = fernet.encrypt(b"SERVER_IP:10.0.0.1")
        assert decrypt_payload(token[:-4], fernet) is None

    def test_wrong_key_rejected(self, fernet):
        other = Fernet(Fernet.generate_key())
        assert decrypt_payload(other.encrypt(b"x"), fernet) is None

    def test_garbage_and_wrong_type_rejected(self, fernet):
        assert decrypt_payload(b"\xff\x00garbage", fernet) is None
        assert decrypt_payload(b"", fernet) is None


class TestNonceHelpers:
    def test_new_nonce_is_random_hex(self):
        a, b = new_nonce(), new_nonce()
        assert a != b
        assert len(a) == 32
        int(a, 16)

    def test_request_plaintext_and_split(self):
        n = new_nonce()
        assert build_request_plaintext(b"DISCOVER_SERVER", n) == b"DISCOVER_SERVER|" + n
        assert split_response_nonce(b"SERVER_IP:1.2.3.4:8000|" + n) == (
            b"SERVER_IP:1.2.3.4:8000",
            n,
        )
        assert split_response_nonce(b"SERVER_IP:1.2.3.4") == (b"SERVER_IP:1.2.3.4", None)

    def test_nonce_matches(self):
        n = new_nonce()
        assert nonce_matches(n, n)
        assert not nonce_matches(None, n)
        assert not nonce_matches(new_nonce(), n)


class TestReceiveResponsesNonce:
    def _config(self, key, **kw):
        return ClientConfig(encryption_enabled=True, secret_key=key, **kw)

    def _sock(self, *packets):
        sock = MagicMock()
        sock.recvfrom.side_effect = [(p, ("10.0.0.1", 9999)) for p in packets] + [
            socket.timeout
        ]
        return sock

    def test_matching_nonce_accepted_and_stripped(self, key, fernet):
        nonce = new_nonce()
        sock = self._sock(fernet.encrypt(b"SERVER_IP:10.0.0.1:8000|" + nonce))
        results = receive_responses(sock, self._config(key), expected_nonce=nonce)
        assert len(results) == 1
        assert (results[0].ip, results[0].port) == ("10.0.0.1", 8000)
        assert results[0].raw_response == b"SERVER_IP:10.0.0.1:8000"

    def test_mismatched_nonce_rejected(self, key, fernet):
        sock = self._sock(fernet.encrypt(b"SERVER_IP:10.0.0.1|" + new_nonce()))
        results = receive_responses(sock, self._config(key), expected_nonce=new_nonce())
        assert results == []

    def test_missing_nonce_rejected_when_expected(self, key, fernet):
        sock = self._sock(fernet.encrypt(b"SERVER_IP:10.0.0.1"))
        results = receive_responses(sock, self._config(key), expected_nonce=new_nonce())
        assert results == []

    def test_replayed_response_from_earlier_round_rejected(self, key, fernet):
        """A captured, still-fresh response for another request is not accepted."""
        old_round, this_round = new_nonce(), new_nonce()
        captured = fernet.encrypt(b"SERVER_IP:10.6.6.6|" + old_round)
        genuine = fernet.encrypt(b"SERVER_IP:10.0.0.1|" + this_round)
        sock = self._sock(captured, genuine)
        results = receive_responses(sock, self._config(key), expected_nonce=this_round)
        assert [r.ip for r in results] == ["10.0.0.1"]

    def test_expired_response_rejected(self, key, fernet):
        nonce = new_nonce()
        old = fernet.encrypt_at_time(b"SERVER_IP:10.0.0.1|" + nonce, int(time.time()) - 300)
        sock = self._sock(old)
        results = receive_responses(sock, self._config(key), expected_nonce=nonce)
        assert results == []

    def test_configured_ttl_is_used(self, key, fernet):
        nonce = new_nonce()
        aged = fernet.encrypt_at_time(b"SERVER_IP:10.0.0.1|" + nonce, int(time.time()) - 100)
        strict = receive_responses(
            self._sock(aged), self._config(key), expected_nonce=nonce
        )
        lenient = receive_responses(
            self._sock(aged),
            self._config(key, encryption_ttl=300),
            expected_nonce=nonce,
        )
        assert strict == []
        assert len(lenient) == 1

    def test_bit_flipped_response_rejected(self, key, fernet):
        nonce = new_nonce()
        token = fernet.encrypt(b"SERVER_IP:10.0.0.1|" + nonce)
        sock = self._sock(_flip_bit(token, 30))
        results = receive_responses(sock, self._config(key), expected_nonce=nonce)
        assert results == []


class TestMultiInterfaceNonce:
    @patch("discovery_client.network.socket.receive_responses")
    @patch("discovery_client.network.socket.send_discovery_request")
    @patch("discovery_client.network.socket.create_discovery_socket")
    @patch("discovery_client.network.socket.detect_segmented_network", return_value=None)
    @patch("discovery_client.network.socket.select_interfaces")
    def test_one_nonce_per_round_distinct_tokens(
        self, mock_select, _mock_seg, mock_create, mock_send, mock_recv, key, fernet
    ):
        mock_select.return_value = [
            InterfaceInfo(name="en0", ip="192.168.1.10", netmask="255.255.255.0"),
            InterfaceInfo(name="en1", ip="10.0.0.10", netmask="255.255.255.0"),
        ]
        mock_create.return_value = MagicMock()
        mock_recv.return_value = []
        config = ClientConfig(encryption_enabled=True, secret_key=key)

        discover_servers_multi_interface(config)

        tokens = [c.args[1] for c in mock_send.call_args_list]
        assert len(tokens) == 2
        assert tokens[0] != tokens[1]
        nonces = {fernet.decrypt(t).partition(b"|")[2] for t in tokens}
        assert len(nonces) == 1
        assert mock_recv.call_args.kwargs["expected_nonce"] == nonces.pop()


class TestTtlConfig:
    def test_defaults(self):
        cfg = ClientConfig()
        assert cfg.encryption_ttl == 30.0
        assert cfg.encryption_clock_skew == 10.0

    @pytest.mark.parametrize("ttl", [0, -1])
    def test_invalid_ttl(self, ttl):
        with pytest.raises(ValueError):
            ClientConfig(encryption_ttl=ttl)

    def test_invalid_skew(self):
        with pytest.raises(ValueError):
            ClientConfig(encryption_clock_skew=-1)

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("DISCOVERY_CLIENT_ENCRYPTION_TTL", "45")
        monkeypatch.setenv("DISCOVERY_CLIENT_ENCRYPTION_CLOCK_SKEW", "2.5")
        cfg = load_config()
        assert cfg.encryption_ttl == 45.0
        assert cfg.encryption_clock_skew == 2.5

    def test_from_env_invalid(self, monkeypatch):
        monkeypatch.setenv("DISCOVERY_CLIENT_ENCRYPTION_TTL", "soon")
        with pytest.raises(ValueError):
            load_config()
