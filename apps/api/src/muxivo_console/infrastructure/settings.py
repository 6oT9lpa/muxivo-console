"""Fail-fast, environment-backed settings for the production composition root."""

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.fernet import Fernet


class ConfigurationError(ValueError):
    """Raised before serving traffic when a required production setting is unsafe."""


@dataclass(frozen=True, slots=True)
class ConsoleSettings:
    database_url: str
    email_lookup_key: bytes
    email_encryption_key: bytes
    session_token_pepper: bytes
    discord_control_base_url: str
    discord_control_signing_key: bytes
    environment: str = "production"

    @property
    def allow_insecure_discord_control_http(self) -> bool:
        return self.environment == "development"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "ConsoleSettings":
        values = environment if environment is not None else os.environ
        database_url = _required(values, "MUXIVO_CONSOLE_DATABASE_URL")
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ConfigurationError("MUXIVO_CONSOLE_DATABASE_URL must use postgresql+asyncpg.")
        runtime_environment = values.get("MUXIVO_CONSOLE_ENVIRONMENT", "production")
        if runtime_environment not in {"development", "staging", "production"}:
            raise ConfigurationError("MUXIVO_CONSOLE_ENVIRONMENT is invalid.")
        encryption_key = _required(values, "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY").encode()
        try:
            Fernet(encryption_key)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY must be a valid Fernet key."
            ) from error
        return cls(
            database_url=database_url,
            email_lookup_key=_decode_key(values, "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY"),
            email_encryption_key=encryption_key,
            session_token_pepper=_decode_key(values, "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER"),
            discord_control_base_url=_required(values, "MUXIVO_DISCORD_CONTROL_BASE_URL"),
            discord_control_signing_key=_decode_key(values, "MUXIVO_DISCORD_CONTROL_SIGNING_KEY"),
            environment=runtime_environment,
        )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "")
    if not value.strip():
        raise ConfigurationError(f"{name} must be configured.")
    return value


def _decode_key(values: Mapping[str, str], name: str) -> bytes:
    try:
        decoded = base64.b64decode(_required(values, name), validate=True)
    except binascii.Error as error:
        raise ConfigurationError(f"{name} must be base64-encoded.") from error
    if len(decoded) < 32:
        raise ConfigurationError(f"{name} must contain at least 32 bytes.")
    return decoded
