"""SQLAlchemy account projections for Console-owned first-party authentication."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import (
    EmailPasswordAccount,
    LoginIdentityProfile,
    LoginIdentityProvider,
    PasswordCredential,
    UserStatus,
)
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    LoginIdentityRecord,
    PasswordCredentialRecord,
    UserEmailRecord,
    UserRecord,
)


class SqlAlchemyEmailPasswordAccountReader:
    """Read only the credential projection needed for a password verification."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None:
        statement = (
            select(UserRecord.id, UserRecord.status, PasswordCredentialRecord.password_hash)
            .join(UserEmailRecord, UserEmailRecord.user_id == UserRecord.id)
            .join(PasswordCredentialRecord, PasswordCredentialRecord.user_id == UserRecord.id)
            .where(UserEmailRecord.email_lookup_hash == email_lookup_hash)
        )
        async with self._session_factory() as database_session:
            result = await database_session.execute(statement)
            row = result.one_or_none()
        if row is None:
            return None
        try:
            return EmailPasswordAccount(
                user_id=row[0], status=UserStatus(row[1]), password_hash=row[2]
            )
        except ValueError:
            return None


class SqlAlchemyUserEmailLookupReader:
    """Resolve encrypted-email lookup hashes to active first-party user IDs."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_active_user_id_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> UUID | None:
        statement = (
            select(UserRecord.id)
            .join(UserEmailRecord, UserEmailRecord.user_id == UserRecord.id)
            .where(
                UserEmailRecord.email_lookup_hash == email_lookup_hash,
                UserRecord.status == UserStatus.ACTIVE.value,
            )
        )
        async with self._session_factory() as database_session:
            value = (await database_session.execute(statement)).scalar_one_or_none()
        return value if isinstance(value, UUID) else None


class SqlAlchemyLoginIdentityReader:
    """Read a provider subject already verified and owned by this Console user."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_provider_subject(
        self, *, user_id: UUID, provider: LoginIdentityProvider
    ) -> str | None:
        statement = select(LoginIdentityRecord.provider_subject).where(
            LoginIdentityRecord.user_id == user_id,
            LoginIdentityRecord.provider == provider.value,
        )
        async with self._session_factory() as database_session:
            result = await database_session.execute(statement)
            value = result.scalar_one_or_none()
        return value if isinstance(value, str) and value else None

    async def find_user_id(
        self, *, provider: LoginIdentityProvider, provider_subject: str
    ) -> UUID | None:
        statement = select(LoginIdentityRecord.user_id).where(
            LoginIdentityRecord.provider == provider.value,
            LoginIdentityRecord.provider_subject == provider_subject,
        )
        async with self._session_factory() as database_session:
            value = (await database_session.execute(statement)).scalar_one_or_none()
        return value if isinstance(value, UUID) else None

    async def list_for_user(self, *, user_id: UUID) -> tuple[LoginIdentityProfile, ...]:
        statement = (
            select(LoginIdentityRecord)
            .where(LoginIdentityRecord.user_id == user_id)
            .order_by(LoginIdentityRecord.linked_at, LoginIdentityRecord.id)
        )
        async with self._session_factory() as database_session:
            records = (await database_session.execute(statement)).scalars().all()
        identities: list[LoginIdentityProfile] = []
        for record in records:
            try:
                identities.append(
                    LoginIdentityProfile(
                        id=record.id,
                        user_id=record.user_id,
                        provider=LoginIdentityProvider(record.provider),
                        linked_at=record.linked_at,
                        last_used_at=record.last_used_at,
                    )
                )
            except ValueError:
                continue
        return tuple(identities)


class SqlAlchemyPasswordCredentialRepository:
    """Read and rotate first-party password credentials without exposing plaintext."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_for_user(self, *, user_id: UUID) -> PasswordCredential | None:
        statement = select(PasswordCredentialRecord.password_hash).where(
            PasswordCredentialRecord.user_id == user_id
        )
        async with self._session_factory() as database_session:
            password_hash = (await database_session.execute(statement)).scalar_one_or_none()
        if not isinstance(password_hash, str):
            return None
        try:
            return PasswordCredential(user_id=user_id, password_hash=password_hash)
        except ValueError:
            return None

    async def change_password(
        self, *, user_id: UUID, password_hash: str, changed_at, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as database_session:
                async with database_session.begin():
                    result = await database_session.execute(
                        update(PasswordCredentialRecord)
                        .where(PasswordCredentialRecord.user_id == user_id)
                        .values(
                            password_hash=password_hash,
                            password_changed_at=changed_at,
                            failed_attempts=0,
                            locked_until=None,
                        )
                    )
                    if result.rowcount != 1:
                        return False
                    database_session.add(
                        AuditEventRecord(
                            id=audit_event.id,
                            correlation_id=audit_event.correlation_id,
                            actor_id=audit_event.actor_id,
                            organization_id=audit_event.organization_id,
                            action=audit_event.action,
                            resource_type=audit_event.resource_type,
                            resource_id=audit_event.resource_id,
                            result=audit_event.result,
                        )
                    )
                    await database_session.flush()
        except IntegrityError:
            return False
        return True
