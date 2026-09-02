import logging

from fastapi.testclient import TestClient
from muxivo_console.presentation.api import BrowserSecurityPolicy, create_app


def test_api_responses_include_browser_security_headers() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_development_security_policy_disables_hsts() -> None:
    client = TestClient(create_app(browser_security_policy=BrowserSecurityPolicy.development()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")


def test_cors_allowlist_allows_only_configured_origins() -> None:
    client = TestClient(
        create_app(
            browser_security_policy=BrowserSecurityPolicy(
                cors_allowed_origins=("https://console.muxivo.test",)
            )
        )
    )

    allowed = client.options(
        "/healthz",
        headers={
            "Origin": "https://console.muxivo.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/healthz",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://console.muxivo.test"
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_unhandled_errors_return_redacted_generic_response(caplog) -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("access_token=discord-access-token")

    caplog.set_level(logging.ERROR, logger="muxivo_console.presentation.api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["X-Correlation-ID"]
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert "discord-access-token" not in response.text
    assert "discord-access-token" not in caplog.text
    assert "http.unhandled_error" in caplog.text
