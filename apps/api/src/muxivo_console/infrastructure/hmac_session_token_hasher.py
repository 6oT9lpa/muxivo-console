"""Keyed browser session token hashing adapter."""

import hashlib
import hmac


class HmacSessionTokenHasher:
    """Hash raw session tokens with a separately managed server-side pepper."""

    def __init__(self, pepper: bytes) -> None:
        if len(pepper) < 32:
            raise ValueError("Session token pepper must contain at least 256 bits.")
        self._pepper = pepper

    def hash(self, raw_token: str) -> str:
        return hmac.new(self._pepper, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()
