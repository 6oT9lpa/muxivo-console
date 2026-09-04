"""Complete password recovery with a one-time opaque token."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.complete_password_recovery_command import (
    CompletePasswordRecoveryCommand,
)
from muxivo_console.application.password_recovery_completion_rejected_error import (
    PasswordRecoveryCompletionRejectedError,
)
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    PasswordHasher,
    PasswordRecoveryCompletionNotifier,
    PasswordRecoveryCompletionWriter,
    PasswordRecoveryRecipientReader,
    SessionTokenHasher,
)

logger = logging.getLogger("muxivo_console.application.complete_password_recovery")


@dataclass(slots=True)
class CompletePasswordRecovery:
    """Consume a recovery token and persist a new password credential."""

    identifiers: IdentifierGenerator
    clock: Clock
    token_hasher: SessionTokenHasher
    password_hasher: PasswordHasher
    completions: PasswordRecoveryCompletionWriter
    recipients: PasswordRecoveryRecipientReader
    notifier: PasswordRecoveryCompletionNotifier

    async def execute(self, command: CompletePasswordRecoveryCommand) -> None:
        logger.info(
            "password.recovery.complete.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        if not _is_usable_token(command.token):
            logger.warning(
                "password.recovery.complete.rejected_token_shape",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")
        if not _is_valid_password(command.new_password):
            logger.warning(
                "password.recovery.complete.rejected_password_policy",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")

        completed_at = self.clock.now()
        user_id = await self.completions.complete(
            token_hash=self.token_hasher.hash(command.token),
            password_hash=self.password_hasher.hash(command.new_password),
            completed_at=completed_at,
            audit_id=self.identifiers.new(),
            correlation_id=command.correlation_id,
        )
        if user_id is None:
            logger.warning(
                "password.recovery.complete.rejected",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")
        recipient_email = await self.recipients.find_primary_email(user_id=user_id)
        if recipient_email is None:
            logger.error(
                "password.recovery.completion_notification.recipient_unavailable",
                extra={
                    "user_id": str(user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
        else:
            try:
                await self.notifier.send(
                    user_id=user_id,
                    recipient_email=recipient_email,
                    changed_at=completed_at,
                    correlation_id=command.correlation_id,
                )
            except Exception as error:
                logger.error(
                    "password.recovery.completion_notification.delivery_failed",
                    extra={
                        "user_id": str(user_id),
                        "correlation_id": str(command.correlation_id),
                        "error_type": type(error).__name__,
                    },
                )
        logger.info(
            "password.recovery.complete.completed",
            extra={
                "user_id": str(user_id),
                "correlation_id": str(command.correlation_id),
            },
        )


def _is_usable_token(token: str) -> bool:
    if not token or len(token) > 4096:
        return False
    return not any(character.isspace() for character in token)


def _is_valid_password(password: str) -> bool:
    return 12 <= len(password) <= 1024
