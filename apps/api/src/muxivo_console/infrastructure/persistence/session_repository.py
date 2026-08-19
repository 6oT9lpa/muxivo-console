"""SQLAlchemy session persistence; raw browser bearer tokens never reach this layer."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy import select
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
            return AuthSession(
                id=record.id,
                user_id=record.user_id,
                token_hash=record.token_hash,
                expires_at=record.expires_at,
                assurance_level=SessionAssuranceLevel(record.assurance_level),
                revoked_at=record.revoked_at,
                authenticated_at=record.created_at,
            )
        except ValueError:
            return None
