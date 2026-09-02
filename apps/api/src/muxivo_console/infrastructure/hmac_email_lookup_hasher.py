"""Keyed email lookup hashing adapter."""

import hashlib
import hmac


class HmacEmailLookupHasher:
    """Derive a stable keyed lookup value without retaining plaintext email."""

    def __init__(self, lookup_key: bytes) -> None:
        if len(lookup_key) < 32:
            raise ValueError("Email lookup key must contain at least 256 bits.")
        self._lookup_key = lookup_key

    def lookup_hash(self, normalized_email: str) -> str:
        return hmac.new(
            self._lookup_key, normalized_email.encode("utf-8"), hashlib.sha256
        ).hexdigest()
