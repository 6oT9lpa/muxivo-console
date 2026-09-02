"""SQLAlchemy session persistence; raw browser bearer tokens never reach this layer."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel
from muxivo_console.infrastructure.persistence.models import AuditEventRecord, AuthSessionRecord


class SqlAlchemyAuthSessionWriter:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(self, *, session: AuthSession, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as database_session:
                async with database_session.begin():
                    database_session.add_all(
                        (
                            AuthSessionRecord(
                                id=session.id,
                                user_id=session.user_id,
                                token_hash=session.token_hash,
                                expires_at=session.expires_at,
                                revoked_at=session.revoked_at,
                                assurance_level=session.assurance_level.value,
                                ip_hash=session.ip_hash,
                                user_agent_hash=session.user_agent_hash,
                                last_seen_at=session.last_seen_at,
                                created_at=session.authenticated_at,
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
                    await database_session.flush()
        except IntegrityError:
            return False
        return True


class SqlAlchemyAuthSessionReader:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_by_token_hash(self, *, token_hash: str) -> AuthSession | None:
        async with self._session_factory() as database_session:
            result = await database_session.execute(
                select(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash)
            )
            record = result.scalar_one_or_none()
        if record is None:
            return None
        try:
            return _session_from_record(record)
        except ValueError:
            return None


class SqlAlchemyAuthSessionListingReader:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_active_for_user(self, *, user_id: UUID, active_at) -> tuple[AuthSession, ...]:
        statement = (
            select(AuthSessionRecord)
            .where(
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at > active_at,
            )
            .order_by(AuthSessionRecord.last_seen_at.desc().nullslast(), AuthSessionRecord.id)
        )
        async with self._session_factory() as database_session:
            records = (await database_session.execute(statement)).scalars().all()
        sessions: list[AuthSession] = []
        for record in records:
            try:
                sessions.append(_session_from_record(record))
            except ValueError:
                continue
        return tuple(sessions)


class SqlAlchemyAuthSessionRevoker:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def revoke(self, *, session_id, user_id, revoked_at, audit_event: AuditEvent) -> bool:
        statement = (
            update(AuthSessionRecord)
            .where(
                AuthSessionRecord.id == session_id,
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
                if result.rowcount != 1:
                    return False
                session.add(
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
        return True

    async def revoke_all_for_user(
        self, *, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> int:
        statement = (
            update(AuthSessionRecord)
            .where(
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at > revoked_at,
            )
            .values(revoked_at=revoked_at)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
                revoked_count = int(result.rowcount or 0)
                if revoked_count < 1:
                    return 0
                session.add(
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
        return revoked_count


class SqlAlchemyAuthSessionReauthenticationWriter:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def reauthenticate(
        self, *, session_id: UUID, user_id: UUID, authenticated_at, audit_event: AuditEvent
    ) -> bool:
        statement = (
            update(AuthSessionRecord)
            .where(
                AuthSessionRecord.id == session_id,
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at > authenticated_at,
            )
            .values(
                assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION.value,
                created_at=authenticated_at,
                last_seen_at=authenticated_at,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
                if result.rowcount != 1:
                    return False
                session.add(
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
        return True


def _session_from_record(record: AuthSessionRecord) -> AuthSession:
    return AuthSession(
        id=record.id,
        user_id=record.user_id,
        token_hash=record.token_hash,
        expires_at=record.expires_at,
        assurance_level=SessionAssuranceLevel(record.assurance_level),
        revoked_at=record.revoked_at,
        authenticated_at=record.created_at,
        last_seen_at=record.last_seen_at,
        ip_hash=record.ip_hash,
        user_agent_hash=record.user_agent_hash,
    )
