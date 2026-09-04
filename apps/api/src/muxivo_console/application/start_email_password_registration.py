"""Start and resend the verified e-mail/password registration flow."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from cryptography.fernet import InvalidToken

from muxivo_console.application.email_password_registration_verification_result import (
    EmailPasswordRegistrationVerificationResult,
)
from muxivo_console.application.pending_email_password_registration import (
    MAX_VERIFICATION_ATTEMPTS,
    PendingEmailPasswordRegistration,
)
from muxivo_console.application.ports import (
    Clock,
    EmailAddressNormalizer,
    EmailPasswordAccountReader,
    EmailPasswordRegistrationVerificationNotifier,
    EmailProtector,
    IdentifierGenerator,
    OneTimeTokenStore,
    OpaqueSessionTokenIssuer,
    PasswordHasher,
    SessionTokenHasher,
)
from muxivo_console.application.resend_email_password_registration_command import (
    ResendEmailPasswordRegistrationCommand,
)
from muxivo_console.application.start_email_password_registration_command import (
    StartEmailPasswordRegistrationCommand,
)

logger = logging.getLogger("muxivo_console.application.start_email_password_registration")


@dataclass(slots=True)
class StartEmailPasswordRegistration:
    """Issue a short-lived pending token and deliver a six-digit code."""

    identifiers: IdentifierGenerator
    clock: Clock
    email_normalizer: EmailAddressNormalizer
    email_protector: EmailProtector
    password_hasher: PasswordHasher
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    accounts: EmailPasswordAccountReader
    pending_registrations: OneTimeTokenStore
    notifier: EmailPasswordRegistrationVerificationNotifier
    lifetime: timedelta = timedelta(minutes=15)

    async def execute(
        self, command: StartEmailPasswordRegistrationCommand
    ) -> EmailPasswordRegistrationVerificationResult:
        logger.info(
            "auth.email_password.verification.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        normalized_email = self.email_normalizer.normalize(command.email)
        self._validate_display_name(command.display_name)
        self._validate_password(command.password)
        lookup_hash = self.email_protector.lookup_hash(normalized_email)
        account = await self.accounts.find_by_email_lookup_hash(email_lookup_hash=lookup_hash)
        if account is not None:
            logger.info(
                "auth.email_password.verification.completed_without_delivery",
                extra={"correlation_id": str(command.correlation_id)},
            )
            return self._result(None)

        raw_token = self.token_issuer.issue()
        code = _new_verification_code()
        pending = PendingEmailPasswordRegistration(
            registration_id=self.identifiers.new(),
            email_ciphertext=self.email_protector.encrypt(normalized_email),
            email_lookup_hash=lookup_hash,
            password_hash=self.password_hasher.hash(command.password),
            display_name=command.display_name,
            verification_code_hash=self._code_hash(raw_token, code),
        )
        pending_value = pending.to_json()
        stored = await self.pending_registrations.put(
            key=self._key(raw_token),
            value=pending_value,
            ttl_seconds=self._lifetime_seconds,
        )
        if not stored:
            logger.warning(
                "auth.email_password.verification.storage_conflict",
                extra={"correlation_id": str(command.correlation_id)},
            )
            return self._result(None)
        try:
            await self.notifier.send(
                registration_id=pending.registration_id,
                recipient_email=normalized_email,
                verification_code=code,
                expires_at=self.clock.now() + self.lifetime,
                correlation_id=command.correlation_id,
            )
        except ConnectionError as error:
            await self._discard_pending(
                key=self._key(raw_token),
                value=pending_value,
                correlation_id=command.correlation_id,
            )
            logger.error(
                "auth.email_password.verification.delivery_unavailable",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise
        except Exception as error:
            await self._discard_pending(
                key=self._key(raw_token),
                value=pending_value,
                correlation_id=command.correlation_id,
            )
            logger.error(
                "auth.email_password.verification.delivery_failed",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise ConnectionError("Registration verification delivery failed.") from error
        logger.info(
            "auth.email_password.verification.completed",
            extra={"correlation_id": str(command.correlation_id)},
        )
        return self._result(raw_token)

    async def resend(
        self, command: ResendEmailPasswordRegistrationCommand
    ) -> EmailPasswordRegistrationVerificationResult:
        """Rotate the code while retaining the same opaque pending-flow token."""
        logger.info(
            "auth.email_password.verification.resend_started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        raw_token = command.token
        current_value = await self.pending_registrations.get(key=self._key(raw_token))
        pending = (
            PendingEmailPasswordRegistration.from_json(current_value) if current_value else None
        )
        if pending is None or pending.attempts >= MAX_VERIFICATION_ATTEMPTS:
            logger.info(
                "auth.email_password.verification.resend_completed_without_delivery",
                extra={"correlation_id": str(command.correlation_id)},
            )
            return EmailPasswordRegistrationVerificationResult(None, self._lifetime_seconds)
        try:
            normalized_email = self.email_protector.decrypt(pending.email_ciphertext)
        except (InvalidToken, TypeError, ValueError) as error:
            logger.error(
                "auth.email_password.verification.resend_state_invalid",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            return EmailPasswordRegistrationVerificationResult(None, self._lifetime_seconds)
        code = _new_verification_code()
        rotated = PendingEmailPasswordRegistration(
            registration_id=pending.registration_id,
            email_ciphertext=pending.email_ciphertext,
            email_lookup_hash=pending.email_lookup_hash,
            password_hash=pending.password_hash,
            display_name=pending.display_name,
            verification_code_hash=self._code_hash(raw_token, code),
            attempts=pending.attempts,
        )
        replaced = await self.pending_registrations.replace(
            key=self._key(raw_token),
            value=rotated.to_json(),
            ttl_seconds=self._lifetime_seconds,
        )
        if not replaced:
            return EmailPasswordRegistrationVerificationResult(None, self._lifetime_seconds)
        rotated_value = rotated.to_json()
        try:
            await self.notifier.send(
                registration_id=rotated.registration_id,
                recipient_email=normalized_email,
                verification_code=code,
                expires_at=self.clock.now() + self.lifetime,
                correlation_id=command.correlation_id,
            )
        except ConnectionError as error:
            await self._discard_pending(
                key=self._key(raw_token),
                value=rotated_value,
                correlation_id=command.correlation_id,
            )
            logger.error(
                "auth.email_password.verification.resend_delivery_unavailable",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise
        except Exception as error:
            await self._discard_pending(
                key=self._key(raw_token),
                value=rotated_value,
                correlation_id=command.correlation_id,
            )
            logger.error(
                "auth.email_password.verification.resend_delivery_failed",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise ConnectionError("Registration verification delivery failed.") from error
        logger.info(
            "auth.email_password.verification.resend_completed",
            extra={"correlation_id": str(command.correlation_id)},
        )
        return self._result(raw_token)

    async def _discard_pending(self, *, key: str, value: str, correlation_id: UUID) -> None:
        try:
            await self.pending_registrations.consume(key=key, value=value)
        except Exception as error:
            logger.error(
                "auth.email_password.verification.cleanup_failed",
                extra={
                    "correlation_id": str(correlation_id),
                    "error_type": type(error).__name__,
                },
            )

    @property
    def _lifetime_seconds(self) -> int:
        return max(60, int(self.lifetime.total_seconds()))

    def _key(self, raw_token: str) -> str:
        return f"muxivo-console:registration-verification:{self.token_hasher.hash(raw_token)}"

    def _code_hash(self, raw_token: str, code: str) -> str:
        return self.token_hasher.hash(f"registration-code:{raw_token}:{code}")

    @staticmethod
    def _validate_display_name(display_name: str) -> None:
        if not display_name.strip() or len(display_name) > 64:
            raise ValueError("Registration display name does not meet policy.")

    @staticmethod
    def _validate_password(password: str) -> None:
        if not 12 <= len(password) <= 1024:
            raise ValueError("Registration password does not meet policy.")

    def _result(self, raw_token: str | None) -> EmailPasswordRegistrationVerificationResult:
        return EmailPasswordRegistrationVerificationResult(raw_token, self._lifetime_seconds)


def _new_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
