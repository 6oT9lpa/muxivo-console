"""Local cryptographic adapters. Production key management is injected by config."""

import hashlib
import hmac
import secrets
import time
from uuid import UUID

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from email_validator import EmailNotValidError, validate_email


class Uuid7IdentifierGenerator:
    """Generate RFC 9562 UUIDv7 values without client control over identifiers."""

    def new(self) -> UUID:
        timestamp_ms = int(time.time() * 1000)
        random_bits = secrets.randbits(74)
        value = (timestamp_ms << 80) | (0b0111 << 76) | (random_bits & ((1 << 76) - 1))
        value = (value & ~(0b11 << 62)) | (0b10 << 62)
        return UUID(int=value)


class ValidatedEmailAddressNormalizer:
    def normalize(self, value: str) -> str:
        try:
            return validate_email(value, check_deliverability=False).normalized
        except EmailNotValidError as error:
            raise ValueError("Email address is invalid.") from error


class HmacEmailLookupHasher:
    """Derive a stable keyed lookup value without retaining an email in plaintext."""

    def __init__(self, lookup_key: bytes) -> None:
        if len(lookup_key) < 32:
            raise ValueError("Email lookup key must contain at least 256 bits.")
        self._lookup_key = lookup_key

    def lookup_hash(self, normalized_email: str) -> str:
        return hmac.new(
            self._lookup_key, normalized_email.encode("utf-8"), hashlib.sha256
        ).hexdigest()


class Argon2idPasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, plaintext_password: str) -> str:
        return self._hasher.hash(plaintext_password)

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, plaintext_password)
        except (InvalidHashError, VerificationError):
            return False
