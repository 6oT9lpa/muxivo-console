"""Create a first-party Muxivo e-mail/password account."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailPasswordRegistrationWriter,
    EmailProtector,
    IdentifierGenerator,
    PasswordHasher,
)
from muxivo_console.application.register_email_password_command import RegisterEmailPasswordCommand
from muxivo_console.application.registration_rejected_error import RegistrationRejectedError
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import (
    EmailPasswordRegistration,
    LoginIdentity,
    LoginIdentityProvider,
    PasswordCredential,
    User,
    UserEmail,
    UserStatus,
)

logger = logging.getLogger("muxivo_console.application.register_email_password")


@dataclass(slots=True)
class RegisterEmailPassword:
    """Register a user and all first-party identity records atomically."""

    identifiers: IdentifierGenerator
    email_normalizer: EmailAddressNormalizer
    email_protector: EmailProtector
    password_hasher: PasswordHasher
    registrations: EmailPasswordRegistrationWriter

    async def execute(self, command: RegisterEmailPasswordCommand) -> UUID:
        logger.info(
            "auth.email_password.registration.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        normalized_email = self.email_normalizer.normalize(command.email)
        self._validate_password(command.password)

        user_id = self.identifiers.new()
        lookup_hash = self.email_protector.lookup_hash(normalized_email)
        registration = EmailPasswordRegistration(
            user=User(
                id=user_id,
                status=UserStatus.ACTIVE,
                display_name=command.display_name,
            ),
            identity=LoginIdentity(
                id=self.identifiers.new(),
                user_id=user_id,
                provider=LoginIdentityProvider.EMAIL,
                provider_subject=lookup_hash,
            ),
            email=UserEmail(
                id=self.identifiers.new(),
                user_id=user_id,
                ciphertext=self.email_protector.encrypt(normalized_email),
                lookup_hash=lookup_hash,
            ),
            password_credential=PasswordCredential(
                user_id=user_id,
                password_hash=self.password_hasher.hash(command.password),
            ),
        )
        created = await self.registrations.register(
            registration=registration,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=user_id,
                organization_id=None,
                action="auth.email_password_registration",
                resource_type="user",
                resource_id=str(user_id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "auth.email_password.registration.rejected_conflict",
                extra={
                    "correlation_id": str(command.correlation_id),
                    "user_id": str(user_id),
                },
            )
            raise RegistrationRejectedError("Registration could not be completed.")
        logger.info(
            "auth.email_password.registration.completed",
            extra={
                "correlation_id": str(command.correlation_id),
                "user_id": str(user_id),
            },
        )
        return user_id

    @staticmethod
    def _validate_password(password: str) -> None:
        if not 12 <= len(password) <= 1024:
            raise RegistrationRejectedError("Registration could not be completed.")
