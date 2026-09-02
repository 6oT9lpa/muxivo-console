"""Complete password recovery with a one-time opaque token."""

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    PasswordHasher,
    PasswordRecoveryCompletionWriter,
    SessionTokenHasher,
)

logger = logging.getLogger(__name__)


class PasswordRecoveryCompletionRejectedError(PermissionError):
    """Safe failure for invalid, expired or already consumed recovery tokens."""


@dataclass(frozen=True, slots=True)
class CompletePasswordRecoveryCommand:
    token: str
    new_password: str
    correlation_id: UUID


@dataclass(slots=True)
class CompletePasswordRecovery:
    identifiers: IdentifierGenerator
    clock: Clock
    token_hasher: SessionTokenHasher
    password_hasher: PasswordHasher
    completions: PasswordRecoveryCompletionWriter

    async def execute(self, command: CompletePasswordRecoveryCommand) -> None:
        logger.info(
            "password.recovery.complete.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        if not self._is_usable_token(command.token):
            logger.warning(
                "password.recovery.complete.rejected_token_shape",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")
        if not self._is_valid_password(command.new_password):
            logger.warning(
                "password.recovery.complete.rejected_password_policy",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")

        completed = await self.completions.complete(
            token_hash=self.token_hasher.hash(command.token),
            password_hash=self.password_hasher.hash(command.new_password),
            completed_at=self.clock.now(),
            audit_id=self.identifiers.new(),
            correlation_id=command.correlation_id,
        )
        if not completed:
            logger.warning(
                "password.recovery.complete.rejected",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise PasswordRecoveryCompletionRejectedError("Password recovery failed.")
        logger.info(
            "password.recovery.complete.completed",
            extra={"correlation_id": str(command.correlation_id)},
        )

    @staticmethod
    def _is_usable_token(token: str) -> bool:
        return (
            bool(token)
            and len(token) <= 4096
            and not any(character.isspace() for character in token)
        )

    @staticmethod
    def _is_valid_password(password: str) -> bool:
        return 12 <= len(password) <= 1024
