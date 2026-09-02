"""Change a first-party password behind recent authentication and audit."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.change_email_password_command import ChangeEmailPasswordCommand
from muxivo_console.application.password_change_rejected_error import PasswordChangeRejectedError
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    PasswordCredentialReader,
    PasswordCredentialWriter,
    PasswordHasher,
    UserStatusReader,
)
from muxivo_console.application.require_recent_authentication_use_case import (
    RequireRecentAuthentication,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus

logger = logging.getLogger("muxivo_console.application.change_email_password")


@dataclass(slots=True)
class ChangeEmailPassword:
    """Change the password only after session and credential checks succeed."""

    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    credentials: PasswordCredentialReader
    credential_writer: PasswordCredentialWriter
    password_hasher: PasswordHasher
    recent_authentication: RequireRecentAuthentication

    async def execute(self, command: ChangeEmailPasswordCommand) -> None:
        actor_id = command.principal.user_id
        logger.info(
            "password.change.started",
            extra={
                "actor_id": str(actor_id),
                "session_id": str(command.principal.session_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        try:
            self.recent_authentication.check(command.principal)
        except PermissionError:
            logger.warning(
                "password.change.denied_recent_authentication",
                extra={
                    "actor_id": str(actor_id),
                    "session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise
        if await self.user_statuses.get_status(user_id=actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "password.change.denied_inactive_user",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")
        if not self._is_valid_new_password(command.new_password):
            logger.warning(
                "password.change.rejected_password_policy",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")
        credential = await self.credentials.find_for_user(user_id=actor_id)
        if credential is None:
            self.password_hasher.hash(command.current_password)
            logger.warning(
                "password.change.missing_password_identity",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")
        if not self.password_hasher.verify(credential.password_hash, command.current_password):
            logger.warning(
                "password.change.denied_current_password",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")
        if command.current_password == command.new_password:
            logger.warning(
                "password.change.denied_reused_password",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")

        changed = await self.credential_writer.change_password(
            user_id=actor_id,
            password_hash=self.password_hasher.hash(command.new_password),
            changed_at=self.clock.now(),
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=actor_id,
                organization_id=None,
                action="auth.password_changed",
                resource_type="user",
                resource_id=str(actor_id),
                result="succeeded",
            ),
        )
        if not changed:
            logger.warning(
                "password.change.conflict",
                extra={
                    "actor_id": str(actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PasswordChangeRejectedError("Password change failed.")
        logger.info(
            "password.change.completed",
            extra={
                "actor_id": str(actor_id),
                "correlation_id": str(command.correlation_id),
            },
        )

    @staticmethod
    def _is_valid_new_password(password: str) -> bool:
        return 12 <= len(password) <= 1024
