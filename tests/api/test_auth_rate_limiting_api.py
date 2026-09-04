import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from muxivo_console.application.begin_oauth_login import StartedOAuthLogin
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.application.ports import RateLimitDecision
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.infrastructure.session_fingerprint import HmacSessionFingerprintHasher
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class DenyingRateLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def check(self, *, scope: str, key: str) -> RateLimitDecision:
        self.calls.append((scope, key))
        return RateLimitDecision(allowed=False, retry_after_seconds=17)


class RecordingUseCase:
    def __init__(self, result=None) -> None:
        self.result = result
        self.called = False

    async def execute(self, *args, **kwargs):
        self.called = True
        return self.result


class LoginUseCase(RecordingUseCase):
    async def execute(self, command):
        self.called = True
        return IssuedBrowserSession(
            id=uuid4(),
            raw_token="opaque-session",
            raw_csrf_token="csrf-token",
            expires_at=datetime(2026, 8, 20, tzinfo=UTC) + timedelta(days=14),
            assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
        )


class SessionResolver:
    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            uuid4(),
            uuid4(),
            SessionAssuranceLevel.PASSWORD,
            datetime(2026, 8, 22, tzinfo=UTC),
        )


def assert_rate_limited(response, limiter: DenyingRateLimiter, expected_scope: str) -> None:
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests"}
    assert response.headers["Retry-After"] == "17"
    assert limiter.calls[0][0] == expected_scope
    assert limiter.calls[0][1]


@pytest.mark.parametrize(
    ("path", "json_payload", "expected_scope"),
    (
        (
            "/api/v1/auth/email-password/registrations",
            {
                "email": "creator@example.com",
                "password": "a-long-enough-password",
                "display_name": "Creator",
            },
            "auth.registration",
        ),
        (
            "/api/v1/auth/email-password/registration-verifications",
            {"token": "opaque-pending-token", "code": "123456"},
            "auth.registration.verification",
        ),
        (
            "/api/v1/auth/email-password/registration-verifications/resend",
            {"token": "opaque-pending-token"},
            "auth.registration.resend",
        ),
        (
            "/api/v1/auth/email-password/sessions",
            {"email": "creator@example.com", "password": "a-long-enough-password"},
            "auth.login",
        ),
        (
            "/api/v1/auth/password-recovery/requests",
            {"email": "creator@example.com"},
            "auth.password_recovery.request",
        ),
        (
            "/api/v1/auth/password-recovery/completions",
            {"token": "opaque-recovery-token", "new_password": "new-secure-password"},
            "auth.password_recovery.complete",
        ),
    ),
)
def test_auth_mutation_endpoints_are_rate_limited_before_use_case(
    path: str, json_payload: dict[str, str], expected_scope: str
) -> None:
    limiter = DenyingRateLimiter()
    use_case = RecordingUseCase()
    login_use_case = LoginUseCase()
    app = create_app(
        registration_verification_start_use_case=use_case,
        registration_verification_use_case=use_case,
        authentication_use_case=login_use_case,
        password_recovery_request_use_case=use_case,
        password_recovery_completion_use_case=use_case,
        rate_limiter=limiter,
    )
    client = TestClient(app)

    response = client.post(path, json=json_payload)

    assert_rate_limited(response, limiter, expected_scope)
    assert use_case.called is False
    assert login_use_case.called is False


def test_discord_oauth_start_is_rate_limited_before_use_case() -> None:
    limiter = DenyingRateLimiter()
    use_case = RecordingUseCase(StartedOAuthLogin("state", "challenge", 600))
    app = create_app(
        discord_login_start=use_case,
        discord_authorization_url=lambda **_: "https://discord.example/authorize",
        rate_limiter=limiter,
    )
    client = TestClient(app)

    response = client.post("/api/v1/auth/discord/authorizations")

    assert_rate_limited(response, limiter, "auth.oauth.start")
    assert use_case.called is False


def test_discord_oauth_callback_is_rate_limited_before_use_case() -> None:
    limiter = DenyingRateLimiter()
    use_case = RecordingUseCase()
    app = create_app(discord_identity_link_complete=use_case, rate_limiter=limiter)
    client = TestClient(app)

    response = client.get("/api/v1/auth/discord/callback?code=oauth-code&state=oauth-state")

    assert_rate_limited(response, limiter, "auth.oauth.callback")
    assert use_case.called is False


def test_session_reauthentication_is_rate_limited_before_use_case() -> None:
    limiter = DenyingRateLimiter()
    use_case = RecordingUseCase()
    app = create_app(
        session_resolver=SessionResolver(),
        session_reauthentication_use_case=use_case,
        rate_limiter=limiter,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.post(
        "/api/v1/auth/session/reauthentications",
        headers={CSRF_HEADER_NAME: "csrf-token"},
        json={"current_password": "correct-password"},
    )

    assert_rate_limited(response, limiter, "auth.reauthentication")
    assert use_case.called is False


def test_rate_limit_logs_use_a_fingerprint_instead_of_raw_client_address(caplog) -> None:
    limiter = DenyingRateLimiter()
    caplog.set_level(logging.INFO, logger="muxivo_console.presentation.api")
    app = create_app(
        registration_verification_start_use_case=RecordingUseCase(),
        rate_limiter=limiter,
        session_fingerprint_hasher=HmacSessionFingerprintHasher(b"p" * 32),
    )

    response = TestClient(app).post(
        "/api/v1/auth/email-password/registrations",
        json={
            "email": "creator@example.com",
            "password": "a-long-enough-password",
            "display_name": "Creator",
        },
    )

    assert response.status_code == 429
    denial_record = next(
        record for record in caplog.records if record.message == "auth.rate_limit.denied"
    )
    assert denial_record.client_fingerprint.startswith("ip:")
    assert not hasattr(denial_record, "client_host")
    assert "testclient" not in caplog.text
