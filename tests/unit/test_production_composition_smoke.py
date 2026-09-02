import pytest
from muxivo_console.infrastructure.settings import ConfigurationError, ConsoleSettings

from scripts.production_composition_smoke import (
    production_smoke_environment,
    run_fail_fast_smoke,
    run_production_composition_smoke,
)


def test_production_composition_smoke_builds_browser_safe_app() -> None:
    run_production_composition_smoke(production_smoke_environment())


@pytest.mark.parametrize(
    ("variable", "value"),
    (
        ("MUXIVO_CONSOLE_PUBLIC_BASE_URL", None),
        ("MUXIVO_CONSOLE_SECRET_SOURCE", ".env"),
        ("MUXIVO_CONSOLE_RATE_LIMIT_BACKEND", "memory"),
        ("MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS", None),
        ("MUXIVO_DISCORD_OAUTH_REDIRECT_URI", "http://x"),
        ("MUXIVO_TWITCH_OAUTH_CLIENT_ID", None),
        ("MUXIVO_TWITCH_OAUTH_REDIRECT_URI", "http://x"),
    ),
)
def test_production_smoke_environment_fails_fast_for_unsafe_values(
    variable: str,
    value: str | None,
) -> None:
    environment = production_smoke_environment()
    if value is None:
        environment.pop(variable, None)
    else:
        environment[variable] = value

    with pytest.raises(ConfigurationError):
        ConsoleSettings.from_environment(environment)


def test_production_fail_fast_smoke_covers_unsafe_environment_cases() -> None:
    run_fail_fast_smoke()
