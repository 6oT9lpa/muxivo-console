import logging
from uuid import UUID

from fastapi.testclient import TestClient
from muxivo_console.application.register_email_password import RegistrationRejectedError
from muxivo_console.presentation.api import create_app


class RecordingRegistrationUseCase:
    def __init__(self, should_reject: bool = False) -> None:
        self.should_reject = should_reject
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.should_reject:
            raise RegistrationRejectedError("Registration could not be completed.")
        return UUID("019fe7ed-a611-7200-ba7a-2387a9e15c75")


def payload() -> dict[str, str]:
    return {
        "email": "creator@example.com",
        "password": "a-long-enough-password",
        "display_name": "Creator",
    }


def test_registration_endpoint_uses_versioned_enumeration_safe_contract() -> None:
    registration = RecordingRegistrationUseCase()
    client = TestClient(create_app(registration_use_case=registration))

    response = client.post("/api/v1/auth/email-password/registrations", json=payload())

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert UUID(response.headers["X-Correlation-ID"]).version == 4
    assert registration.command.email == "creator@example.com"
    assert registration.command.password == "a-long-enough-password"
    assert registration.command.display_name == "Creator"
    assert registration.command.correlation_id == UUID(response.headers["X-Correlation-ID"])


def test_registration_conflict_has_the_same_public_response(caplog) -> None:
    client = TestClient(create_app(registration_use_case=RecordingRegistrationUseCase(True)))

    caplog.set_level(logging.INFO, logger="muxivo_console.presentation.api")
    response = client.post("/api/v1/auth/email-password/registrations", json=payload())

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert "auth.email_password_registration.rejected" in caplog.text
    assert "creator@example.com" not in caplog.text
    assert "a-long-enough-password" not in caplog.text


def test_registration_is_unavailable_without_explicit_secure_runtime_wiring() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/auth/email-password/registrations", json=payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Registration is unavailable"}
