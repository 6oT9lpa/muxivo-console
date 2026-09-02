"""Argon2id password hashing adapter."""

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type


class Argon2idPasswordHasher:
    """Hash and verify passwords with the Console's Argon2id policy."""

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
