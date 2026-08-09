"""Transactional SQLAlchemy adapter for first-party email/password registration."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import EmailPasswordRegistration
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    LoginIdentityRecord,
    PasswordCredentialRecord,
    UserEmailRecord,
    UserRecord,
)


class SqlAlchemyEmailPasswordRegistrationWriter:
    """Write identity records and audit data in one database transaction.

    A database uniqueness conflict is deliberately reduced to ``False``. The
    application layer maps it to a public response that does not enumerate
    whether an e-mail address or provider identity already exists.
    """

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def register(
        self, *, registration: EmailPasswordRegistration, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(
                        (
                            UserRecord(
                                id=registration.user.id,
                                status=registration.user.status.value,
                                display_name=registration.user.display_name,
                            ),
                            LoginIdentityRecord(
                                id=registration.identity.id,
                                user_id=registration.identity.user_id,
                                provider=registration.identity.provider.value,
                                provider_subject=registration.identity.provider_subject,
                            ),
                            UserEmailRecord(
                                id=registration.email.id,
                                user_id=registration.email.user_id,
                                email_ciphertext=registration.email.ciphertext,
                                email_lookup_hash=registration.email.lookup_hash,
                                is_primary=registration.email.is_primary,
                            ),
                            PasswordCredentialRecord(
                                user_id=registration.password_credential.user_id,
                                password_hash=registration.password_credential.password_hash,
                            ),
                            AuditEventRecord(
                                id=audit_event.id,
                                correlation_id=audit_event.correlation_id,
                                actor_id=audit_event.actor_id,
                                organization_id=audit_event.organization_id,
                                action=audit_event.action,
                                resource_type=audit_event.resource_type,
                                resource_id=audit_event.resource_id,
                                result=audit_event.result,
                            ),
                        )
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True
