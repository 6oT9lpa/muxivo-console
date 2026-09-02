from __future__ import annotations

import ssl
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts.production_network_preflight import (
    REQUIRED_SECURITY_HEADERS,
    NetworkPreflightSettings,
    run_preflight,
    settings_from_environment,
    validate_dns,
    validate_public_http_surface,
)


def _environment(**overrides: str) -> dict[str, str]:
    environment = {
        "MUXIVO_CONSOLE_PUBLIC_BASE_URL": "https://console.muxivo.pro",
        "MUXIVO_CONSOLE_EXPECTED_DNS_IPS": "138.124.119.238",
    }
    environment.update(overrides)
    return environment


def test_settings_require_https_origin_and_expected_ip() -> None:
    settings = settings_from_environment(_environment())

    assert settings.hostname == "console.muxivo.pro"
    assert settings.expected_dns_ips == frozenset({"138.124.119.238"})
    assert settings.timeout_seconds == 10


def test_settings_reject_nonstandard_https_port() -> None:
    with pytest.raises(ValueError, match="standard HTTPS port"):
        settings_from_environment(
            _environment(MUXIVO_CONSOLE_PUBLIC_BASE_URL="https://console.muxivo.pro:8443")
        )


@pytest.mark.parametrize(
    "overrides",
    (
        {"MUXIVO_CONSOLE_PUBLIC_BASE_URL": "http://console.muxivo.pro"},
        {"MUXIVO_CONSOLE_PUBLIC_BASE_URL": "https://user:pass@console.muxivo.pro"},
        {"MUXIVO_CONSOLE_PUBLIC_BASE_URL": "https://console.muxivo.pro/api"},
        {"MUXIVO_CONSOLE_EXPECTED_DNS_IPS": "not-an-ip"},
        {"MUXIVO_CONSOLE_NETWORK_PREFLIGHT_TIMEOUT_SECONDS": "0"},
    ),
)
def test_settings_reject_unsafe_or_ambiguous_values(overrides: Mapping[str, str]) -> None:
    with pytest.raises(ValueError):
        settings_from_environment(_environment(**overrides))


def test_dns_validation_requires_approved_ingress_address() -> None:
    settings = settings_from_environment(_environment())

    def resolver(host: str, port: int, *, type: int) -> list[tuple[Any, ...]]:
        assert host == "console.muxivo.pro"
        assert port == 443
        assert type
        return [
            (2, 1, 6, "", ("138.124.119.238", 443)),
            (2, 1, 6, "", ("203.0.113.20", 443)),
        ]

    assert validate_dns(settings, resolver=resolver) == frozenset(
        {"138.124.119.238", "203.0.113.20"}
    )


def test_dns_validation_rejects_missing_approved_ingress_address() -> None:
    settings = settings_from_environment(_environment())

    with pytest.raises(OSError, match="approved ingress"):
        validate_dns(
            settings,
            resolver=lambda *_args, **_kwargs: [
                (2, 1, 6, "", ("203.0.113.20", 443)),
            ],
        )


def test_public_surface_requires_health_endpoints_and_security_headers() -> None:
    settings = settings_from_environment(_environment())
    headers = {header: "configured" for header in REQUIRED_SECURITY_HEADERS}
    calls: list[str] = []

    def http_getter(
        _settings: NetworkPreflightSettings,
        path: str,
    ) -> tuple[int, Mapping[str, str], str]:
        calls.append(path)
        body = '<meta name="muxivo-app" content="console" />' if path == "/" else "{}"
        return 200, headers, body

    validate_public_http_surface(settings, http_getter=http_getter)

    assert calls == ["/", "/healthz", "/readyz"]


def test_public_surface_rejects_missing_security_header() -> None:
    settings = settings_from_environment(_environment())
    headers = {header: "configured" for header in REQUIRED_SECURITY_HEADERS}
    headers.pop("content-security-policy")

    with pytest.raises(OSError, match="security headers"):
        validate_public_http_surface(
            settings,
            http_getter=lambda *_args: (
                200,
                headers,
                '<meta name="muxivo-app" content="console" />',
            ),
        )


def test_public_surface_checks_security_headers_on_each_endpoint() -> None:
    settings = settings_from_environment(_environment())
    complete_headers = {header: "configured" for header in REQUIRED_SECURITY_HEADERS}
    calls: list[str] = []

    def http_getter(
        _settings: NetworkPreflightSettings,
        path: str,
    ) -> tuple[int, Mapping[str, str], str]:
        calls.append(path)
        if path == "/readyz":
            return 200, {}, "{}"
        body = '<meta name="muxivo-app" content="console" />' if path == "/" else "{}"
        return 200, complete_headers, body

    with pytest.raises(OSError, match="public surface"):
        validate_public_http_surface(settings, http_getter=http_getter)

    assert calls == ["/", "/healthz", "/readyz"]


def test_run_preflight_reports_failed_stages_without_revealing_values(caplog) -> None:
    settings = settings_from_environment(_environment())
    caplog.set_level("INFO", logger="muxivo_console.production_network_preflight")

    def raise_tls(_settings: NetworkPreflightSettings) -> None:
        raise ssl.SSLError("certificate mismatch")

    failures = run_preflight(
        settings,
        dns_resolver=lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("203.0.113.20", 443)),
        ],
        tls_validator=raise_tls,
        http_getter=lambda *_args: (
            200,
            {},
            '<meta name="muxivo-app" content="console" />',
        ),
    )

    assert failures == ("dns", "tls", "public_http_surface")
    assert "certificate mismatch" not in caplog.text
    assert "138.124.119.238" not in caplog.text


def test_public_surface_rejects_a_neighboring_site_on_the_console_host() -> None:
    settings = settings_from_environment(_environment())
    headers = {header: "configured" for header in REQUIRED_SECURITY_HEADERS}

    def http_getter(
        _settings: NetworkPreflightSettings,
        path: str,
    ) -> tuple[int, Mapping[str, str], str]:
        body = "<title>Muxivo Discord</title>" if path == "/" else "{}"
        return 200, headers, body

    with pytest.raises(OSError, match="frontend identity marker"):
        validate_public_http_surface(settings, http_getter=http_getter)


def test_script_has_no_repository_local_output_dependency() -> None:
    script = Path("scripts/production_network_preflight.py")

    assert script.exists()
    assert "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD" not in script.read_text(
        encoding="utf-8"
    )
