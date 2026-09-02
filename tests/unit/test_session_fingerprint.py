import pytest
from muxivo_console.infrastructure.session_fingerprint import HmacSessionFingerprintHasher


def test_session_fingerprints_are_keyed_stable_and_domain_separated() -> None:
    hasher = HmacSessionFingerprintHasher(b"p" * 32)

    ip_fingerprint = hasher.hash_ip_address("203.0.113.10")
    same_ip_fingerprint = hasher.hash_ip_address("203.0.113.10")
    user_agent_fingerprint = hasher.hash_user_agent("Mozilla/5.0")

    assert ip_fingerprint == same_ip_fingerprint
    assert len(ip_fingerprint) == 64
    assert ip_fingerprint != user_agent_fingerprint
    assert "203.0.113.10" not in ip_fingerprint
    assert "Mozilla/5.0" not in user_agent_fingerprint


def test_session_fingerprint_hasher_rejects_a_short_pepper() -> None:
    with pytest.raises(ValueError, match="at least 256 bits"):
        HmacSessionFingerprintHasher(b"short")
