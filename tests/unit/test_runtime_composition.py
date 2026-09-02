import base64
from types import SimpleNamespace

import muxivo_console.infrastructure.composition as composition_module
import pytest
from cryptography.fernet import Fernet
from muxivo_console.domain.activity import Platform
from muxivo_console.infrastructure.composition import (
    create_development_app,
    create_production_app,
)
from muxivo_console.infrastructure.naming import RandomSuffixOrganizationSlugGenerator
from muxivo_console.infrastructure.settings import ConfigurationError, ConsoleSettings


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
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_USERNAME": "smtp-user",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD": "smtp-password",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_FROM_EMAIL": "security@muxivo.test",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE": "https://console.muxivo.test/recover",
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
    assert ConsoleSettings.from_environment(values).allow_insecure_twitch_control_http is True
    assert (
        ConsoleSettings.from_environment(environment()).allow_insecure_discord_control_http is False
    )
    assert (
        ConsoleSettings.from_environment(environment()).allow_insecure_twitch_control_http is False
    )


def test_settings_parse_optional_twitch_control_api_configuration() -> None:
    values = environment()
    key = values["MUXIVO_DISCORD_CONTROL_SIGNING_KEY"]
    values["MUXIVO_TWITCH_CONTROL_BASE_URL"] = "https://twitch-control.internal"
    values["MUXIVO_TWITCH_CONTROL_SIGNING_KEY"] = key

    settings = ConsoleSettings.from_environment(values)

    assert settings.twitch_control is not None
    assert settings.twitch_control.base_url == "https://twitch-control.internal"
    assert settings.twitch_control.signing_key == base64.b64decode(key)

    values = environment()
    values["MUXIVO_TWITCH_CONTROL_BASE_URL"] = "https://twitch-control.internal"
    with pytest.raises(ConfigurationError, match="Twitch Control API configuration"):
        ConsoleSettings.from_environment(values)


def test_settings_require_deployment_readiness_values_outside_development() -> None:
    values = environment()
    del values["MUXIVO_CONSOLE_PUBLIC_BASE_URL"]

    with pytest.raises(ConfigurationError, match="PUBLIC_BASE_URL"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_PUBLIC_BASE_URL"] = "http://localhost:5173"
    with pytest.raises(ConfigurationError, match="HTTPS URL"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_SECRET_SOURCE"] = ".env"
    with pytest.raises(ConfigurationError, match="production secret manager"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_SECRET_SOURCE"] = "spreadsheet"
    with pytest.raises(ConfigurationError, match="SECRET_SOURCE"):
        ConsoleSettings.from_environment(values)

    settings = ConsoleSettings.from_environment(environment())

    assert settings.deployment is not None
    assert settings.deployment.public_base_url == "https://console.muxivo.test"
    assert settings.deployment.secret_source == "hashicorp-vault"


def test_settings_require_discord_oauth_outside_development() -> None:
    values = environment()
    for name in tuple(values):
        if name.startswith("MUXIVO_DISCORD_OAUTH_"):
            del values[name]

    with pytest.raises(ConfigurationError, match="Discord OAuth"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_DISCORD_OAUTH_REDIRECT_URI"] = (
        "http://console.muxivo.test/api/v1/auth/discord/callback"
    )
    with pytest.raises(ConfigurationError, match="REDIRECT_URI"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_DISCORD_OAUTH_REDIRECT_URI"] = (
        "https://console.muxivo.test/api/v1/identity-links/discord/callback"
    )
    with pytest.raises(ConfigurationError, match="/api/v1/auth/discord/callback"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"
    for name in tuple(values):
        if name.startswith("MUXIVO_DISCORD_OAUTH_"):
            del values[name]

    assert ConsoleSettings.from_environment(values).discord_oauth is None


def test_settings_require_twitch_oauth_outside_development() -> None:
    values = environment()
    for name in tuple(values):
        if name.startswith("MUXIVO_TWITCH_OAUTH_"):
            del values[name]

    with pytest.raises(ConfigurationError, match="Twitch OAuth"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_TWITCH_OAUTH_REDIRECT_URI"] = (
        "http://console.muxivo.test/api/v1/auth/twitch/callback"
    )
    with pytest.raises(ConfigurationError, match="TWITCH_OAUTH_REDIRECT_URI"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_TWITCH_OAUTH_REDIRECT_URI"] = (
        "https://console.muxivo.test/api/v1/identity-links/twitch/callback"
    )
    with pytest.raises(ConfigurationError, match="/api/v1/auth/twitch/callback"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"
    for name in tuple(values):
        if name.startswith("MUXIVO_TWITCH_OAUTH_"):
            del values[name]

    assert ConsoleSettings.from_environment(values).twitch_oauth is None


def test_settings_parse_cors_allowlist_and_reject_wildcards() -> None:
    values = environment()
    values["MUXIVO_CONSOLE_PUBLIC_BASE_URL"] = "https://console.muxivo.com"
    values["MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS"] = (
        "https://console.muxivo.com, https://staging-console.muxivo.com/"
    )

    settings = ConsoleSettings.from_environment(values)

    assert settings.cors_allowed_origins == (
        "https://console.muxivo.com",
        "https://staging-console.muxivo.com",
    )

    values["MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS"] = "*"
    with pytest.raises(ConfigurationError, match="must not contain"):
        ConsoleSettings.from_environment(values)


def test_settings_reject_insecure_cors_origin_outside_development() -> None:
    values = environment()
    del values["MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS"]

    with pytest.raises(ConfigurationError, match="CORS_ALLOWED_ORIGINS"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS"] = "https://admin.muxivo.test"

    with pytest.raises(ConfigurationError, match="PUBLIC_BASE_URL"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"

    with pytest.raises(ConfigurationError, match="must use HTTPS"):
        ConsoleSettings.from_environment(values)

    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    assert ConsoleSettings.from_environment(values).cors_allowed_origins == (
        "http://localhost:5173",
    )


def test_settings_require_shared_rate_limiter_outside_development() -> None:
    values = environment()
    del values["MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL"]

    with pytest.raises(ConfigurationError, match="RATE_LIMIT_REDIS_URL"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_RATE_LIMIT_BACKEND"] = "memory"
    with pytest.raises(ConfigurationError, match="only allowed in development"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"
    del values["MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL"]

    settings = ConsoleSettings.from_environment(values)

    assert settings.rate_limit is not None
    assert settings.rate_limit.backend == "memory"


def test_settings_parse_redis_rate_limiter_configuration() -> None:
    settings = ConsoleSettings.from_environment(environment())

    assert settings.rate_limit is not None
    assert settings.rate_limit.backend == "redis"
    assert settings.rate_limit.redis_url == "redis://rate-limit.internal:6379/0"

    values = environment()
    values["MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL"] = "http://not-redis"
    with pytest.raises(ConfigurationError, match="RATE_LIMIT_REDIS_URL"):
        ConsoleSettings.from_environment(values)


def test_settings_require_password_recovery_smtp_outside_development() -> None:
    values = environment()
    for name in tuple(values):
        if name.startswith("MUXIVO_CONSOLE_PASSWORD_RECOVERY_"):
            del values[name]

    with pytest.raises(ConfigurationError, match="Password recovery SMTP"):
        ConsoleSettings.from_environment(values)

    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    assert ConsoleSettings.from_environment(values).password_recovery_smtp is None


def test_settings_parse_password_recovery_smtp_and_reject_insecure_values() -> None:
    settings = ConsoleSettings.from_environment(environment())

    assert settings.password_recovery_smtp is not None
    assert settings.password_recovery_smtp.host == "smtp.internal"
    assert settings.password_recovery_smtp.port == 587
    assert settings.password_recovery_smtp.from_email == "security@muxivo.test"

    values = environment()
    values["MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PORT"] = "70000"
    with pytest.raises(ConfigurationError, match="between 1 and 65535"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE"] = "http://console.muxivo.test/recover"
    with pytest.raises(ConfigurationError, match="must use HTTPS"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values["MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_STARTTLS"] = "false"
    with pytest.raises(ConfigurationError, match="STARTTLS"):
        ConsoleSettings.from_environment(values)

    values = environment()
    values.pop("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_USERNAME")
    values.pop("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD")
    with pytest.raises(ConfigurationError, match="authentication is required"):
        ConsoleSettings.from_environment(values)


def test_settings_enable_connection_reconciliation_outside_development() -> None:
    settings = ConsoleSettings.from_environment(environment())

    assert settings.connection_reconciliation is not None
    assert settings.connection_reconciliation.enabled is True
    assert settings.connection_reconciliation.batch_limit == 100

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    assert ConsoleSettings.from_environment(values).connection_reconciliation is None


def test_settings_enable_security_cleanup_outside_development() -> None:
    settings = ConsoleSettings.from_environment(environment())

    assert settings.security_cleanup is not None
    assert settings.security_cleanup.enabled is True
    assert settings.security_cleanup.session_retention_days == 30
    assert settings.security_cleanup.password_recovery_retention_hours == 24

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    assert ConsoleSettings.from_environment(values).security_cleanup is None


def test_settings_parse_connection_reconciliation_controls() -> None:
    values = environment()
    values["MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_SYSTEM_ACTOR_ID"] = (
        "11111111-1111-1111-1111-111111111111"
    )
    values["MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_INTERVAL_SECONDS"] = "45.5"
    values["MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_INITIAL_DELAY_SECONDS"] = "0"
    values["MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_BATCH_LIMIT"] = "25"

    settings = ConsoleSettings.from_environment(values)

    assert settings.connection_reconciliation is not None
    assert str(settings.connection_reconciliation.system_actor_id) == (
        "11111111-1111-1111-1111-111111111111"
    )
    assert settings.connection_reconciliation.interval_seconds == 45.5
    assert settings.connection_reconciliation.initial_delay_seconds == 0
    assert settings.connection_reconciliation.batch_limit == 25

    values["MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_BATCH_LIMIT"] = "0"
    with pytest.raises(ConfigurationError, match="BATCH_LIMIT"):
        ConsoleSettings.from_environment(values)


def test_settings_parse_security_cleanup_controls() -> None:
    values = environment()
    values["MUXIVO_CONSOLE_SECURITY_CLEANUP_INTERVAL_SECONDS"] = "7200.5"
    values["MUXIVO_CONSOLE_SECURITY_CLEANUP_INITIAL_DELAY_SECONDS"] = "0"
    values["MUXIVO_CONSOLE_SECURITY_CLEANUP_SESSION_RETENTION_DAYS"] = "45"
    values["MUXIVO_CONSOLE_SECURITY_CLEANUP_PASSWORD_RECOVERY_RETENTION_HOURS"] = "48"

    settings = ConsoleSettings.from_environment(values)

    assert settings.security_cleanup is not None
    assert settings.security_cleanup.interval_seconds == 7200.5
    assert settings.security_cleanup.initial_delay_seconds == 0
    assert settings.security_cleanup.session_retention_days == 45
    assert settings.security_cleanup.password_recovery_retention_hours == 48

    values["MUXIVO_CONSOLE_SECURITY_CLEANUP_SESSION_RETENTION_DAYS"] = "0"
    with pytest.raises(ConfigurationError, match="SESSION_RETENTION_DAYS"):
        ConsoleSettings.from_environment(values)


def test_production_composition_wires_real_use_cases_without_development_catalog() -> None:
    app = create_production_app(ConsoleSettings.from_environment(environment()))

    assert app.title == "Muxivo Console API"


def test_production_composition_wires_twitch_health_when_control_api_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture_create_app(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(title="Muxivo Console API")

    monkeypatch.setattr(composition_module, "create_app", capture_create_app)
    values = environment()
    key = values["MUXIVO_DISCORD_CONTROL_SIGNING_KEY"]
    values["MUXIVO_TWITCH_CONTROL_BASE_URL"] = "https://twitch-control.internal"
    values["MUXIVO_TWITCH_CONTROL_SIGNING_KEY"] = key

    app = create_production_app(ConsoleSettings.from_environment(values))

    assert app.title == "Muxivo Console API"
    health_use_case = captured["platform_health_use_case"]
    assert Platform.DISCORD in health_use_case.health_readers
    assert Platform.TWITCH in health_use_case.health_readers
    assert captured["twitch_identity_link_start"] is not None
    assert captured["twitch_identity_link_complete"] is not None
    assert captured["twitch_authorization_url"] is not None


def test_development_composition_requires_explicit_development_environment() -> None:
    with pytest.raises(ValueError, match="development settings"):
        create_development_app(ConsoleSettings.from_environment(environment()))

    values = environment()
    values["MUXIVO_CONSOLE_ENVIRONMENT"] = "development"

    app = create_development_app(ConsoleSettings.from_environment(values))

    assert app.title == "Muxivo Console API"


def test_slug_generator_is_server_unique_and_url_safe() -> None:
    generator = RandomSuffixOrganizationSlugGenerator()

    first = generator.generate("Creator community!")
    second = generator.generate("Creator community!")

    assert first.startswith("creator-community-")
    assert first != second
    assert len(first) <= 96
