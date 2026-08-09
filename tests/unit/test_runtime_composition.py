import base64

import pytest
from cryptography.fernet import Fernet
from muxivo_console.infrastructure.composition import create_production_app
from muxivo_console.infrastructure.naming import RandomSuffixOrganizationSlugGenerator
from muxivo_console.infrastructure.settings import ConfigurationError, ConsoleSettings


def environment() -> dict[str, str]:
    key = base64.b64encode(b"k" * 32).decode()
    return {
        "MUXIVO_CONSOLE_DATABASE_URL": "postgresql+asyncpg://console:password@localhost/console",
        "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY": key,
        "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER": key,
        "MUXIVO_DISCORD_CONTROL_BASE_URL": "https://discord-control.internal",
        "MUXIVO_DISCORD_CONTROL_SIGNING_KEY": key,
    }


def test_settings_require_all_security_critical_values() -> None:
    values = environment()
    del values["MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER"]

    with pytest.raises(ConfigurationError, match="SESSION_TOKEN_PEPPER"):
        ConsoleSettings.from_environment(values)


def test_settings_reject_non_async_postgres_and_invalid_fernet_key() -> None:
    values = environment()
    values["MUXIVO_CONSOLE_DATABASE_URL"] = "sqlite+aiosqlite:///console.db"

    with pytest.raises(ConfigurationError, match=r"postgresql\+asyncpg"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY"] = "invalid"
    with pytest.raises(ConfigurationError, match="valid Fernet key"):
        ConsoleSettings.from_environment(values)


def test_development_is_the_only_environment_that_allows_insecure_discord_http() -> None:
    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    assert ConsoleSettings.from_environment(values).allow_insecure_discord_control_http is True
    assert (
        ConsoleSettings.from_environment(environment()).allow_insecure_discord_control_http is False
    )


def test_production_composition_wires_real_use_cases_without_development_catalog() -> None:
    app = create_production_app(ConsoleSettings.from_environment(environment()))

    assert app.title == "Muxivo Console API"


def test_slug_generator_is_server_unique_and_url_safe() -> None:
    generator = RandomSuffixOrganizationSlugGenerator()

    first = generator.generate("Creator community!")
    second = generator.generate("Creator community!")

    assert first.startswith("creator-community-")
    assert first != second
    assert len(first) <= 96
