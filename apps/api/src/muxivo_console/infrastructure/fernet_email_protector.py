"""Fernet email encryption adapter."""

from cryptography.fernet import Fernet, InvalidToken

from muxivo_console.infrastructure.hmac_email_lookup_hasher import HmacEmailLookupHasher


class FernetEmailProtector(HmacEmailLookupHasher):
    """Encrypt email values with an externally managed, rotated data key."""

    def __init__(self, *, lookup_key: bytes, encryption_key: bytes) -> None:
        super().__init__(lookup_key)
        try:
            self._cipher = Fernet(encryption_key)
        except (TypeError, ValueError) as error:
            raise ValueError("Email encryption key must be a valid Fernet key.") from error

    def encrypt(self, normalized_email: str) -> bytes:
        return self._cipher.encrypt(normalized_email.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt only in a privileged application path; never log the result."""
        try:
            return self._cipher.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ValueError("Email ciphertext could not be decrypted.") from error
