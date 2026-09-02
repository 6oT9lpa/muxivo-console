"""Fail-fast, environment-backed settings for the production composition root."""

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from cryptography.fernet import Fernet


class ConfigurationError(ValueError):
    """Raised before serving traffic when a required production setting is unsafe."""


@dataclass(frozen=True, slots=True)
class DiscordOAuthSettings:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True, slots=True)
class TwitchOAuthSettings:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True, slots=True)
class SmtpPasswordRecoverySettings:
    host: str
    port: int
    from_email: str
    reset_url_base: str
    username: str | None = None
    password: str | None = None
    starttls: bool = True


@dataclass(frozen=True, slots=True)
class RateLimitSettings:
    backend: str
    redis_url: str | None = None


@dataclass(frozen=True, slots=True)
class DeploymentReadinessSettings:
    public_base_url: str
    secret_source: str


@dataclass(frozen=True, slots=True)
class ConnectionReconciliationSettings:
    enabled: bool
    system_actor_id: UUID
    interval_seconds: float = 300.0
    initial_delay_seconds: float = 10.0
    batch_limit: int = 100


@dataclass(frozen=True, slots=True)
class SecurityCleanupSettings:
    enabled: bool
    interval_seconds: float = 86_400.0
    initial_delay_seconds: float = 60.0
    session_retention_days: int = 30
    password_recovery_retention_hours: int = 24


@dataclass(frozen=True, slots=True)
class TwitchControlSettings:
    base_url: str
    signing_key: bytes


@dataclass(frozen=True, slots=True)
class ConsoleSettings:
    database_url: str
    email_lookup_key: bytes
    email_encryption_key: bytes
    session_token_pepper: bytes
    discord_control_base_url: str
    discord_control_signing_key: bytes
    environment: str = "production"
    deployment: DeploymentReadinessSettings | None = None
    discord_oauth: DiscordOAuthSettings | None = None
    twitch_oauth: TwitchOAuthSettings | None = None
    rate_limit: RateLimitSettings | None = None
    cors_allowed_origins: tuple[str, ...] = ()
    password_recovery_smtp: SmtpPasswordRecoverySettings | None = None
    connection_reconciliation: ConnectionReconciliationSettings | None = None
    security_cleanup: SecurityCleanupSettings | None = None
    twitch_control: TwitchControlSettings | None = None

    @property
    def allow_insecure_discord_control_http(self) -> bool:
        return self.environment == "development"

    @property
    def allow_insecure_twitch_control_http(self) -> bool:
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
        deployment = _deployment_readiness_settings(values, environment=runtime_environment)
        oauth = _discord_oauth_settings(values, environment=runtime_environment)
        twitch_oauth = _twitch_oauth_settings(values, environment=runtime_environment)
        password_recovery_smtp = _optional_password_recovery_smtp(
            values, environment=runtime_environment
        )
        rate_limit = _rate_limit_settings(values, environment=runtime_environment)
        connection_reconciliation = _connection_reconciliation_settings(
            values, environment=runtime_environment
        )
        security_cleanup = _security_cleanup_settings(values, environment=runtime_environment)
        twitch_control = _optional_twitch_control_settings(values)
        return cls(
            database_url=database_url,
            email_lookup_key=_decode_key(values, "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY"),
            email_encryption_key=encryption_key,
            session_token_pepper=_decode_key(values, "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER"),
            discord_control_base_url=_required(values, "MUXIVO_DISCORD_CONTROL_BASE_URL"),
            discord_control_signing_key=_decode_key(values, "MUXIVO_DISCORD_CONTROL_SIGNING_KEY"),
            environment=runtime_environment,
            deployment=deployment,
            discord_oauth=oauth,
            twitch_oauth=twitch_oauth,
            rate_limit=rate_limit,
            cors_allowed_origins=_optional_cors_allowed_origins(
                values,
                environment=runtime_environment,
                public_base_url=deployment.public_base_url if deployment else None,
            ),
            password_recovery_smtp=password_recovery_smtp,
            connection_reconciliation=connection_reconciliation,
            security_cleanup=security_cleanup,
            twitch_control=twitch_control,
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


def _deployment_readiness_settings(
    values: Mapping[str, str], *, environment: str
) -> DeploymentReadinessSettings | None:
    if environment == "development":
        return None
    public_base_url = _required(values, "MUXIVO_CONSOLE_PUBLIC_BASE_URL").rstrip("/")
    _validate_public_https_url(public_base_url, "MUXIVO_CONSOLE_PUBLIC_BASE_URL")
    secret_source = _required(values, "MUXIVO_CONSOLE_SECRET_SOURCE").strip().lower()
    if secret_source in {"env", ".env", "dotenv", "local", "local-env", "local_env"}:
        raise ConfigurationError(
            "MUXIVO_CONSOLE_SECRET_SOURCE must name a production secret manager "
            "outside development."
        )
    allowed_secret_sources = {
        "aws-secrets-manager",
        "azure-key-vault",
        "doppler",
        "gcp-secret-manager",
        "hashicorp-vault",
        "kubernetes-secrets",
        "onepassword-secrets-automation",
    }
    if secret_source not in allowed_secret_sources:
        raise ConfigurationError(
            "MUXIVO_CONSOLE_SECRET_SOURCE must be one of: "
            f"{', '.join(sorted(allowed_secret_sources))}."
        )
    return DeploymentReadinessSettings(
        public_base_url=public_base_url,
        secret_source=secret_source,
    )


def _validate_public_https_url(value: str, setting_name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError(f"{setting_name} must be an HTTPS URL.")
    hostname = parsed.hostname or ""
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0"} or hostname.endswith(".local"):
        raise ConfigurationError(f"{setting_name} must use a provisioned public domain.")


def _discord_oauth_settings(
    values: Mapping[str, str], *, environment: str
) -> DiscordOAuthSettings | None:
    names = (
        "MUXIVO_DISCORD_OAUTH_CLIENT_ID",
        "MUXIVO_DISCORD_OAUTH_CLIENT_SECRET",
        "MUXIVO_DISCORD_OAUTH_REDIRECT_URI",
    )
    provided = [bool(values.get(name, "").strip()) for name in names]
    if not any(provided):
        if environment != "development":
            raise ConfigurationError("Discord OAuth configuration is required outside development.")
        return None
    if not all(provided):
        raise ConfigurationError("Discord OAuth configuration must be complete or absent.")
    redirect_uri = _required(values, names[2])
    if environment != "development":
        _validate_discord_oauth_redirect_uri(redirect_uri)
    return DiscordOAuthSettings(
        client_id=_required(values, names[0]),
        client_secret=_required(values, names[1]),
        redirect_uri=redirect_uri,
    )


def _twitch_oauth_settings(
    values: Mapping[str, str], *, environment: str
) -> TwitchOAuthSettings | None:
    names = (
        "MUXIVO_TWITCH_OAUTH_CLIENT_ID",
        "MUXIVO_TWITCH_OAUTH_CLIENT_SECRET",
        "MUXIVO_TWITCH_OAUTH_REDIRECT_URI",
    )
    provided = [bool(values.get(name, "").strip()) for name in names]
    if not any(provided):
        if environment != "development":
            raise ConfigurationError("Twitch OAuth configuration is required outside development.")
        return None
    if not all(provided):
        raise ConfigurationError("Twitch OAuth configuration must be complete or absent.")
    redirect_uri = _required(values, names[2])
    if environment != "development":
        _validate_oauth_redirect_uri(
            redirect_uri,
            setting_name="MUXIVO_TWITCH_OAUTH_REDIRECT_URI",
            expected_path="/api/v1/auth/twitch/callback",
        )
    return TwitchOAuthSettings(
        client_id=_required(values, names[0]),
        client_secret=_required(values, names[1]),
        redirect_uri=redirect_uri,
    )


def _validate_discord_oauth_redirect_uri(redirect_uri: str) -> None:
    _validate_oauth_redirect_uri(
        redirect_uri,
        setting_name="MUXIVO_DISCORD_OAUTH_REDIRECT_URI",
        expected_path="/api/v1/auth/discord/callback",
    )


def _validate_oauth_redirect_uri(
    redirect_uri: str, *, setting_name: str, expected_path: str
) -> None:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError(f"{setting_name} must use HTTPS.")
    if parsed.path != expected_path:
        raise ConfigurationError(
            f"{setting_name} must use {expected_path} outside development."
        )


def _optional_twitch_control_settings(values: Mapping[str, str]) -> TwitchControlSettings | None:
    names = (
        "MUXIVO_TWITCH_CONTROL_BASE_URL",
        "MUXIVO_TWITCH_CONTROL_SIGNING_KEY",
    )
    provided = [bool(values.get(name, "").strip()) for name in names]
    if not any(provided):
        return None
    if not all(provided):
        raise ConfigurationError("Twitch Control API configuration must be complete or absent.")
    return TwitchControlSettings(
        base_url=_required(values, names[0]),
        signing_key=_decode_key(values, names[1]),
    )


def _rate_limit_settings(values: Mapping[str, str], *, environment: str) -> RateLimitSettings:
    backend = values.get(
        "MUXIVO_CONSOLE_RATE_LIMIT_BACKEND",
        "memory" if environment == "development" else "redis",
    ).strip().lower()
    if backend not in {"memory", "redis"}:
        raise ConfigurationError("MUXIVO_CONSOLE_RATE_LIMIT_BACKEND must be memory or redis.")
    if backend == "memory":
        if environment != "development":
            raise ConfigurationError(
                "MUXIVO_CONSOLE_RATE_LIMIT_BACKEND=memory is only allowed in development."
            )
        return RateLimitSettings(backend="memory")
    redis_url = _required(values, "MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL")
    if not redis_url.startswith(("redis://", "rediss://")):
        raise ConfigurationError("MUXIVO_CONSOLE_RATE_LIMIT_REDIS_URL must use redis:// or rediss://.")
    return RateLimitSettings(backend="redis", redis_url=redis_url)


def _optional_cors_allowed_origins(
    values: Mapping[str, str], *, environment: str, public_base_url: str | None
) -> tuple[str, ...]:
    raw_value = values.get("MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS", "")
    origins = tuple(origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip())
    if any(origin == "*" for origin in origins):
        raise ConfigurationError("MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS must not contain '*'.")
    if environment != "development":
        if not origins:
            raise ConfigurationError(
                "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS must be configured outside development."
            )
        insecure = [origin for origin in origins if not origin.startswith("https://")]
        if insecure:
            raise ConfigurationError(
                "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS must use HTTPS outside development."
            )
        if public_base_url is not None and public_base_url not in origins:
            raise ConfigurationError(
                "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS must include "
                "MUXIVO_CONSOLE_PUBLIC_BASE_URL."
            )
    return origins


def _optional_password_recovery_smtp(
    values: Mapping[str, str], *, environment: str
) -> SmtpPasswordRecoverySettings | None:
    names = (
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_HOST",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PORT",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_FROM_EMAIL",
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE",
    )
    provided = [bool(values.get(name, "").strip()) for name in names]
    has_any = any(provided) or bool(
        values.get("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_USERNAME", "").strip()
        or values.get("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD", "").strip()
    )
    if not has_any:
        if environment == "development":
            return None
        raise ConfigurationError(
            "Password recovery SMTP must be configured outside development."
        )
    if not all(provided):
        raise ConfigurationError("Password recovery SMTP configuration must be complete.")
    username = values.get("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_USERNAME", "").strip() or None
    password = values.get("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD", "").strip() or None
    if (username is None) != (password is None):
        raise ConfigurationError(
            "Password recovery SMTP username and password must be configured together."
        )
    reset_url_base = _required(
        values, "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE"
    ).rstrip("/")
    if environment != "development" and not reset_url_base.startswith("https://"):
        raise ConfigurationError(
            "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE must use HTTPS outside development."
        )
    starttls = _optional_boolean(
        values,
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_STARTTLS",
        default=True,
    )
    if environment != "development" and not starttls:
        raise ConfigurationError("Password recovery SMTP STARTTLS is required outside development.")
    return SmtpPasswordRecoverySettings(
        host=_required(values, "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_HOST"),
        port=_required_port(values, "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PORT"),
        from_email=_required(values, "MUXIVO_CONSOLE_PASSWORD_RECOVERY_FROM_EMAIL"),
        reset_url_base=reset_url_base,
        username=username,
        password=password,
        starttls=starttls,
    )


def _required_port(values: Mapping[str, str], name: str) -> int:
    raw_value = _required(values, name)
    try:
        port = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a TCP port.") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{name} must be between 1 and 65535.")
    return port


def _optional_boolean(values: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw_value = values.get(name, "").strip().lower()
    if not raw_value:
        return default
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean value.")


def _connection_reconciliation_settings(
    values: Mapping[str, str], *, environment: str
) -> ConnectionReconciliationSettings | None:
    enabled = _optional_boolean(
        values,
        "MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_ENABLED",
        default=environment != "development",
    )
    if not enabled:
        return None
    return ConnectionReconciliationSettings(
        enabled=True,
        system_actor_id=_optional_uuid(
            values,
            "MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_SYSTEM_ACTOR_ID",
            default=UUID("00000000-0000-0000-0000-000000000001"),
        ),
        interval_seconds=_optional_positive_float(
            values,
            "MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_INTERVAL_SECONDS",
            default=300.0,
        ),
        initial_delay_seconds=_optional_non_negative_float(
            values,
            "MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_INITIAL_DELAY_SECONDS",
            default=10.0,
        ),
        batch_limit=_optional_positive_int(
            values,
            "MUXIVO_CONSOLE_CONNECTION_RECONCILIATION_BATCH_LIMIT",
            default=100,
        ),
    )


def _security_cleanup_settings(
    values: Mapping[str, str], *, environment: str
) -> SecurityCleanupSettings | None:
    enabled = _optional_boolean(
        values,
        "MUXIVO_CONSOLE_SECURITY_CLEANUP_ENABLED",
        default=environment != "development",
    )
    if not enabled:
        return None
    return SecurityCleanupSettings(
        enabled=True,
        interval_seconds=_optional_positive_float(
            values,
            "MUXIVO_CONSOLE_SECURITY_CLEANUP_INTERVAL_SECONDS",
            default=86_400.0,
        ),
        initial_delay_seconds=_optional_non_negative_float(
            values,
            "MUXIVO_CONSOLE_SECURITY_CLEANUP_INITIAL_DELAY_SECONDS",
            default=60.0,
        ),
        session_retention_days=_optional_positive_int(
            values,
            "MUXIVO_CONSOLE_SECURITY_CLEANUP_SESSION_RETENTION_DAYS",
            default=30,
        ),
        password_recovery_retention_hours=_optional_positive_int(
            values,
            "MUXIVO_CONSOLE_SECURITY_CLEANUP_PASSWORD_RECOVERY_RETENTION_HOURS",
            default=24,
        ),
    )


def _optional_uuid(values: Mapping[str, str], name: str, *, default: UUID) -> UUID:
    raw_value = values.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return UUID(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a UUID.") from error


def _optional_positive_int(values: Mapping[str, str], name: str, *, default: int) -> int:
    raw_value = values.get(name, "").strip()
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be positive.")
    return parsed


def _optional_positive_float(values: Mapping[str, str], name: str, *, default: float) -> float:
    parsed = _optional_float(values, name, default=default)
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be positive.")
    return parsed


def _optional_non_negative_float(
    values: Mapping[str, str], name: str, *, default: float
) -> float:
    parsed = _optional_float(values, name, default=default)
    if parsed < 0:
        raise ConfigurationError(f"{name} must not be negative.")
    return parsed


def _optional_float(values: Mapping[str, str], name: str, *, default: float) -> float:
    raw_value = values.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number.") from error
