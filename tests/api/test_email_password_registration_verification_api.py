from uuid import UUID

from fastapi.testclient import TestClient
from muxivo_console.application.email_password_registration_verification_rejected_error import (
    EmailPasswordRegistrationVerificationRejectedError,
)
from muxivo_console.application.email_password_registration_verification_result import (
    EmailPasswordRegistrationVerificationResult,
)
from muxivo_console.presentation.api import create_app


class StartUseCase:
    async def execute(self, command):
        self.command = command
        return EmailPasswordRegistrationVerificationResult("pending-token", 900)

    async def resend(self, command):
        self.resend_command = command
        return EmailPasswordRegistrationVerificationResult("pending-token", 900)


class VerifyUseCase:
    def __init__(self, rejects: bool = False) -> None:
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise EmailPasswordRegistrationVerificationRejectedError("invalid")


class UnavailableVerifyUseCase:
    async def execute(self, command):
        raise ConnectionError("redis unavailable")


def registration_payload() -> dict[str, str]:
    return {
        "email": "creator@example.com",
        "password": "a-long-enough-password",
        "display_name": "Creator",
    }


def test_registration_returns_pending_token_without_exposing_registration_data() -> None:
    start = StartUseCase()
    client = TestClient(create_app(registration_verification_start_use_case=start))

    response = client.post(
        "/api/v1/auth/email-password/registrations",
        json=registration_payload(),
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "verification_required",
        "verification_token": "pending-token",
    }
    assert start.command.email == "creator@example.com"
    assert start.command.password == "a-long-enough-password"
    assert isinstance(start.command.correlation_id, UUID)


def test_verification_and_resend_are_csrf_exempt_and_map_commands() -> None:
    start = StartUseCase()
    verify = VerifyUseCase()
    client = TestClient(
        create_app(
            registration_verification_start_use_case=start,
            registration_verification_use_case=verify,
        )
    )

    verified = client.post(
        "/api/v1/auth/email-password/registration-verifications",
        json={"token": "pending-token", "code": "123456"},
    )
    resent = client.post(
        "/api/v1/auth/email-password/registration-verifications/resend",
        json={"token": "pending-token"},
    )

    assert verified.status_code == 200
    assert verified.json() == {"status": "verified"}
    assert resent.status_code == 202
    assert resent.json()["status"] == "verification_required"
    assert verify.command.token == "pending-token"
    assert verify.command.code == "123456"
    assert start.resend_command.token == "pending-token"


def test_invalid_verification_has_one_public_reason() -> None:
    client = TestClient(
        create_app(
            registration_verification_start_use_case=StartUseCase(),
            registration_verification_use_case=VerifyUseCase(rejects=True),
        )
    )

    response = client.post(
        "/api/v1/auth/email-password/registration-verifications",
        json={"token": "pending-token", "code": "123456"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "E-mail verification failed"}


def test_unavailable_verification_store_is_not_reported_as_invalid_code() -> None:
    client = TestClient(
        create_app(
            registration_verification_start_use_case=StartUseCase(),
            registration_verification_use_case=UnavailableVerifyUseCase(),
        )
    )

    response = client.post(
        "/api/v1/auth/email-password/registration-verifications",
        json={"token": "pending-token", "code": "123456"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "E-mail verification is temporarily unavailable"}
