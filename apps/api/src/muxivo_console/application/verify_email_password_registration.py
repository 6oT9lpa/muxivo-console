"""Verify a six-digit code and atomically complete a pending registration."""

from __future__ import annotations

import hmac
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import NoReturn

from cryptography.fernet import InvalidToken

from muxivo_console.application.complete_email_password_registration import (
    CompleteEmailPasswordRegistration,
)
from muxivo_console.application.complete_email_password_registration_command import (
    CompleteEmailPasswordRegistrationCommand,
)
from muxivo_console.application.email_password_registration_rejected_error import (
    EmailPasswordRegistrationRejectedError,
)
from muxivo_console.application.email_password_registration_verification_rejected_error import (
    EmailPasswordRegistrationVerificationRejectedError,
)
from muxivo_console.application.pending_email_password_registration import (
    MAX_VERIFICATION_ATTEMPTS,
    PendingEmailPasswordRegistration,
)
from muxivo_console.application.ports import EmailProtector, OneTimeTokenStore, SessionTokenHasher
from muxivo_console.application.verify_email_password_registration_command import (
    VerifyEmailPasswordRegistrationCommand,
)

logger = logging.getLogger("muxivo_console.application.verify_email_password_registration")


@dataclass(slots=True)
class VerifyEmailPasswordRegistration:
    """Consume the exact Redis value that was checked to prevent replay races."""

    token_hasher: SessionTokenHasher
    email_protector: EmailProtector
    pending_registrations: OneTimeTokenStore
    registrations: CompleteEmailPasswordRegistration
    max_attempts: int = MAX_VERIFICATION_ATTEMPTS
    lifetime: timedelta = timedelta(minutes=15)

    async def execute(self, command: VerifyEmailPasswordRegistrationCommand) -> None:
        logger.info(
            "auth.email_password.verification.check_started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        if not _is_usable_token(command.token) or not re.fullmatch(r"\d{6}", command.code):
            self._reject(command)
        key = self._key(command.token)
        current_value = await self.pending_registrations.get(key=key)
        pending = (
            PendingEmailPasswordRegistration.from_json(current_value) if current_value else None
        )
        if pending is None or pending.attempts >= self.max_attempts:
            self._reject(command)
        expected_hash = self.token_hasher.hash(f"registration-code:{command.token}:{command.code}")
        if not hmac.compare_digest(expected_hash, pending.verification_code_hash):
            next_attempts = min(self.max_attempts, pending.attempts + 1)
            await self.pending_registrations.replace(
                key=key,
                value=pending.with_attempts(next_attempts).to_json(),
                ttl_seconds=self._lifetime_seconds,
            )
            logger.warning(
                "auth.email_password.verification.check_rejected_code",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "attempts": next_attempts,
                },
            )
            self._reject(command)
        consumed = await self.pending_registrations.consume(key=key, value=current_value)
        if not consumed:
            self._reject(command)
        try:
            normalized_email = self.email_protector.decrypt(pending.email_ciphertext)
            await self.registrations.execute(
                CompleteEmailPasswordRegistrationCommand(
                    normalized_email=normalized_email,
                    display_name=pending.display_name,
                    password_hash=pending.password_hash,
                    correlation_id=command.correlation_id,
                )
            )
        except (
            EmailPasswordRegistrationRejectedError,
            InvalidToken,
            TypeError,
            ValueError,
        ) as error:
            logger.warning(
                "auth.email_password.verification.registration_rejected",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise EmailPasswordRegistrationVerificationRejectedError(
                "E-mail verification failed."
            ) from error
        logger.info(
            "auth.email_password.verification.check_completed",
            extra={"correlation_id": str(command.correlation_id)},
        )

    def _key(self, raw_token: str) -> str:
        return f"muxivo-console:registration-verification:{self.token_hasher.hash(raw_token)}"

    @property
    def _lifetime_seconds(self) -> int:
        return max(60, int(self.lifetime.total_seconds()))

    def _reject(self, command: VerifyEmailPasswordRegistrationCommand) -> NoReturn:
        logger.warning(
            "auth.email_password.verification.check_rejected",
            extra={"correlation_id": str(command.correlation_id)},
        )
        raise EmailPasswordRegistrationVerificationRejectedError("E-mail verification failed.")


def _is_usable_token(token: str) -> bool:
    return (
        bool(token) and len(token) <= 4096 and not any(character.isspace() for character in token)
    )
