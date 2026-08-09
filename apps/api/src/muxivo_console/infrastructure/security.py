"""Local cryptographic adapters. Production key management is injected by config."""

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime
from uuid import UUID

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from cryptography.fernet import Fernet, InvalidToken
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


class FernetEmailProtector(HmacEmailLookupHasher):
    """Encrypt e-mails with an externally managed, rotated data key.

    The composition root must retrieve the key from its deployment secret
    manager or KMS. This adapter does not know about environment variables,
    files, or cloud-provider APIs.
    """

    def __init__(self, *, lookup_key: bytes, encryption_key: bytes) -> None:
        super().__init__(lookup_key)
        try:
            self._cipher = Fernet(encryption_key)
        except (TypeError, ValueError) as error:
            raise ValueError("Email encryption key must be a valid Fernet key.") from error

    def encrypt(self, normalized_email: str) -> bytes:
        return self._cipher.encrypt(normalized_email.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt only in a privileged application path; never expose via API logs."""
        try:
            return self._cipher.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ValueError("Email ciphertext could not be decrypted.") from error


class FernetOpaqueValueProtector:
    """Encrypts transient OAuth secrets using an externally managed data key."""

    def __init__(self, encryption_key: bytes) -> None:
        try:
            self._cipher = Fernet(encryption_key)
        except (TypeError, ValueError) as error:
            raise ValueError("Opaque value encryption key must be a valid Fernet key.") from error

    def encrypt(self, plaintext: str) -> bytes:
        return self._cipher.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._cipher.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ValueError("Opaque value ciphertext could not be decrypted.") from error


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


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SecureOpaqueSessionTokenIssuer:
    """Create a 256-bit opaque token suitable for an HttpOnly browser cookie."""

    def issue(self) -> str:
        return secrets.token_urlsafe(32)


class HmacSessionTokenHasher:
    def __init__(self, pepper: bytes) -> None:
        if len(pepper) < 32:
            raise ValueError("Session token pepper must contain at least 256 bits.")
        self._pepper = pepper

    def hash(self, raw_token: str) -> str:
        return hmac.new(self._pepper, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()
