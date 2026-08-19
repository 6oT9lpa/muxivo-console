import base64
import importlib
import sys

import pytest
from cryptography.fernet import Fernet


def environment() -> dict[str, str]:
    key = base64.b64encode(b"k" * 32).decode()
    return {
        "MUXIVO_CONSOLE_DATABASE_URL": "postgresql+asyncpg://console:password@localhost/console",
        "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY": key,
        "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER": key,
        "MUXIVO_DISCORD_CONTROL_BASE_URL": "http://localhost:8030",
        "MUXIVO_DISCORD_CONTROL_SIGNING_KEY": key,
        "MUXIVO_CONSOLE_ENVIRONMENT": "development",
    }


def test_development_asgi_entrypoint_requires_explicit_development_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in environment().items():
        monkeypatch.setenv(name, value)
    sys.modules.pop("muxivo_console.asgi_development", None)

    module = importlib.import_module("muxivo_console.asgi_development")

    assert module.app.title == "Muxivo Console API"


def test_development_asgi_entrypoint_rejects_production_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in environment().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("MUXIVO_CONSOLE_ENVIRONMENT", "production")
    sys.modules.pop("muxivo_console.asgi_development", None)

    with pytest.raises(ValueError, match="development settings"):
        importlib.import_module("muxivo_console.asgi_development")
