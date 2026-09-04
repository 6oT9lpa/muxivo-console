"""Persist a first-party account only after e-mail ownership is proven."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.complete_email_password_registration_command import (
    CompleteEmailPasswordRegistrationCommand,
)
from muxivo_console.application.email_password_registration_rejected_error import (
    EmailPasswordRegistrationRejectedError,
)
from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailPasswordRegistrationWriter,
    EmailProtector,
    IdentifierGenerator,
)
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

logger = logging.getLogger("muxivo_console.application.complete_email_password_registration")


@dataclass(slots=True)
class CompleteEmailPasswordRegistration:
    """Write the account projection at the end of the verified registration flow."""

    identifiers: IdentifierGenerator
    email_normalizer: EmailAddressNormalizer
    email_protector: EmailProtector
    registrations: EmailPasswordRegistrationWriter

    async def execute(self, command: CompleteEmailPasswordRegistrationCommand) -> UUID:
        logger.info(
            "auth.email_password.registration.verified_started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        normalized_email = self.email_normalizer.normalize(command.normalized_email)
        if not command.password_hash.startswith("$argon2id$"):
            raise EmailPasswordRegistrationRejectedError("Registration could not be completed.")

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
                password_hash=command.password_hash,
            ),
        )
        created = await self.registrations.register(
            registration=registration,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=user_id,
                organization_id=None,
                action="auth.email_password_registration_verified",
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
            raise EmailPasswordRegistrationRejectedError("Registration could not be completed.")
        logger.info(
            "auth.email_password.registration.verified_completed",
            extra={
                "correlation_id": str(command.correlation_id),
                "user_id": str(user_id),
            },
        )
        return user_id
