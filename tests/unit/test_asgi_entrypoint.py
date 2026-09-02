import base64
import importlib
import sys

import pytest
from cryptography.fernet import Fernet
from muxivo_console.infrastructure.settings import ConfigurationError


def environment() -> dict[str, str]:
    key = base64.b64encode(b"k" * 32).decode()
    return {
        "MUXIVO_CONSOLE_DATABASE_URL": "postgresql+asyncpg://console:password@localhost/console",
        "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY": key,
        "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER": key,
        "MUXIVO_CONSOLE_PUBLIC_BASE_URL": "https://console.muxivo.test",
        "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS": "https://console.muxivo.test",
        "MUXIVO_CONSOLE_SECRET_SOURCE": "hashicorp-vault",
        "MUXIVO_DISCORD_CONTROL_BASE_URL": "https://discord-control.internal",
        "MUXIVO_DISCORD_CONTROL_SIGNING_KEY": key,
        "MUXIVO_DISCORD_OAUTH_CLIENT_ID": "discord-client-id",
        "MUXIVO_DISCORD_OAUTH_CLIENT_SECRET": "discord-client-secret",
        "MUXIVO_DISCORD_OAUTH_REDIRECT_URI": (
            "https://console.muxivo.test/api/v1/auth/discord/callback"
        ),
        "MUXIVO_TWITCH_OAUTH_CLIENT_ID": "twitch-client-id",
        "MUXIVO_TWITCH_OAUTH_CLIENT_SECRET": "twitch-client-secret",
        "MUXIVO_TWITCH_OAUTH_REDIRECT_URI": (
            "https://console.muxivo.test/api/v1/auth/twitch/callback"
        ),
        "MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL": "redis://rate-limit.internal:6379/0",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_HOST": "smtp.internal",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PORT": "587",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_FROM_EMAIL": "security@muxivo.test",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE": "https://console.muxivo.test/recover",
    }


def import_asgi(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MUXIVO_CONSOLE_DATABASE_URL", raising=False)
    for name, value in environment().items():
        monkeypatch.setenv(name, value)
    sys.modules.pop("muxivo_console.asgi", None)
    return importlib.import_module("muxivo_console.asgi")


def test_asgi_entrypoint_builds_fully_composed_production_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_asgi(monkeypatch)

    assert module.app.title == "Muxivo Console API"


def test_asgi_entrypoint_fails_before_serving_when_required_settings_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in environment():
        monkeypatch.delenv(name, raising=False)
    sys.modules.pop("muxivo_console.asgi", None)

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        importlib.import_module("muxivo_console.asgi")
