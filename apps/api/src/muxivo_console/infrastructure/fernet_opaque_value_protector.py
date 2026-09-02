"""Fernet transient opaque-value encryption adapter."""

from cryptography.fernet import Fernet, InvalidToken


class FernetOpaqueValueProtector:
    """Encrypt transient OAuth values with an externally managed data key."""

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
