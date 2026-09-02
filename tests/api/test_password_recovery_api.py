from uuid import UUID

from fastapi.testclient import TestClient
from muxivo_console.application.complete_password_recovery import (
    PasswordRecoveryCompletionRejectedError,
)
from muxivo_console.presentation.api import create_app


class PasswordRecoveryRequestUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command) -> None:
        self.command = command


class PasswordRecoveryCompletionUseCase:
    def __init__(self, rejects: bool = False) -> None:
        self.rejects = rejects
        self.command = None

    async def execute(self, command) -> None:
        self.command = command
        if self.rejects:
            raise PasswordRecoveryCompletionRejectedError("Recovery failed.")


def test_password_recovery_request_is_anti_enumeration_and_csrf_exempt() -> None:
    use_case = PasswordRecoveryRequestUseCase()
    client = TestClient(create_app(password_recovery_request_use_case=use_case))

    response = client.post(
        "/api/v1/auth/password-recovery/requests",
        json={"email": "creator@example.com"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert use_case.command.email == "creator@example.com"
    assert isinstance(use_case.command.correlation_id, UUID)


def test_password_recovery_completion_maps_token_and_password_without_csrf() -> None:
    use_case = PasswordRecoveryCompletionUseCase()
    client = TestClient(create_app(password_recovery_completion_use_case=use_case))

    response = client.post(
        "/api/v1/auth/password-recovery/completions",
        json={"token": "opaque-recovery-token", "new_password": "new-secure-password"},
    )

    assert response.status_code == 204
    assert use_case.command.token == "opaque-recovery-token"
    assert use_case.command.new_password == "new-secure-password"
    assert isinstance(use_case.command.correlation_id, UUID)


def test_password_recovery_completion_hides_invalid_token_reason() -> None:
    client = TestClient(
        create_app(
            password_recovery_completion_use_case=PasswordRecoveryCompletionUseCase(rejects=True)
        )
    )

    response = client.post(
        "/api/v1/auth/password-recovery/completions",
        json={"token": "opaque-recovery-token", "new_password": "new-secure-password"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Password recovery failed"}
