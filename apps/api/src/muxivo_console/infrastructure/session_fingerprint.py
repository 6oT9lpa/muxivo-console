"""Keyed browser-session fingerprints used by the security screen."""

import hashlib
import hmac


class HmacSessionFingerprintHasher:
    """Hash client metadata without retaining or logging its raw value."""

    def __init__(self, pepper: bytes) -> None:
        if len(pepper) < 32:
            raise ValueError("Session fingerprint pepper must contain at least 256 bits.")
        self._pepper = pepper

    def hash_ip_address(self, ip_address: str) -> str:
        return self._hash("ip", ip_address)

    def hash_user_agent(self, user_agent: str) -> str:
        return self._hash("user-agent", user_agent)

    def _hash(self, category: str, value: str) -> str:
        message = f"muxivo-console:session-fingerprint:{category}:{value}".encode()
        return hmac.new(self._pepper, message, hashlib.sha256).hexdigest()


__all__ = ["HmacSessionFingerprintHasher"]
