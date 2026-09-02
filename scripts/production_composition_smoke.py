"""Smoke-test the production composition root without external network calls."""

import base64
from collections.abc import Mapping

from cryptography.fernet import Fernet
from muxivo_console.infrastructure.composition import create_production_app
from muxivo_console.infrastructure.settings import ConfigurationError, ConsoleSettings


def production_smoke_environment() -> dict[str, str]:
    key = base64.b64encode(b"k" * 32).decode()
    return {
        "MUXIVO_CONSOLE_DATABASE_URL": (
            "postgresql+asyncpg://console:password@db.internal/muxivo_console"
        ),
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
        "MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE": (
            "https://console.muxivo.test/recover"
        ),
    }


def run_production_composition_smoke(
    values: Mapping[str, str] | None = None,
) -> None:
    environment = dict(values or production_smoke_environment())
    settings = ConsoleSettings.from_environment(environment)
    app = create_production_app(settings)

    route_paths = {getattr(route, "path", "") for route in app.routes}
    middleware_names = {middleware.cls.__name__ for middleware in app.user_middleware}

    if app.title != "Muxivo Console API":
        raise AssertionError("Production composition created an unexpected application.")
    if "CORSMiddleware" not in middleware_names:
        raise AssertionError("Production composition must install CORS allowlist middleware.")
    for required_route in (
        "/healthz",
        "/metrics",
        "/api/v1/organizations",
        "/api/v1/auth/discord/callback",
        "/api/v1/auth/twitch/callback",
    ):
        if required_route not in route_paths:
            raise AssertionError(f"Production composition is missing {required_route}.")


def run_fail_fast_smoke() -> None:
    unsafe_cases = (
        ("missing public URL", "MUXIVO_CONSOLE_PUBLIC_BASE_URL", None),
        ("local secret source", "MUXIVO_CONSOLE_SECRET_SOURCE", ".env"),
        ("memory rate limit backend", "MUXIVO_CONSOLE_RATE_LIMIT_BACKEND", "memory"),
        ("missing CORS allowlist", "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS", None),
        ("insecure Discord OAuth redirect", "MUXIVO_DISCORD_OAUTH_REDIRECT_URI", "http://x"),
        ("missing Twitch OAuth client", "MUXIVO_TWITCH_OAUTH_CLIENT_ID", None),
        ("insecure Twitch OAuth redirect", "MUXIVO_TWITCH_OAUTH_REDIRECT_URI", "http://x"),
        (
            "unsupported Discord OAuth redirect path",
            "MUXIVO_DISCORD_OAUTH_REDIRECT_URI",
            "https://console.muxivo.test/api/v1/identity-links/discord/callback",
        ),
        (
            "unsupported Twitch OAuth redirect path",
            "MUXIVO_TWITCH_OAUTH_REDIRECT_URI",
            "https://console.muxivo.test/api/v1/identity-links/twitch/callback",
        ),
    )
    for label, variable, value in unsafe_cases:
        environment = production_smoke_environment()
        if value is None:
            environment.pop(variable, None)
        else:
            environment[variable] = value
        try:
            ConsoleSettings.from_environment(environment)
        except ConfigurationError:
            continue
        raise AssertionError(f"Production settings accepted unsafe case: {label}.")


def main() -> int:
    run_fail_fast_smoke()
    run_production_composition_smoke()
    print("Production composition smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
