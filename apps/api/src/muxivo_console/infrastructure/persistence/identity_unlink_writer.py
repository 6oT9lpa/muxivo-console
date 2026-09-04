"""Transactional persistence for removing non-email login identities."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.infrastructure.persistence.models import AuditEventRecord, LoginIdentityRecord


class SqlAlchemyLoginIdentityUnlinkWriter:
    """Delete one provider identity and its audit event in one transaction."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def unlink(self, *, identity_id: UUID, user_id: UUID, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as database_session:
                async with database_session.begin():
                    result = await database_session.execute(
                        delete(LoginIdentityRecord).where(
                            LoginIdentityRecord.id == identity_id,
                            LoginIdentityRecord.user_id == user_id,
                            LoginIdentityRecord.provider != LoginIdentityProvider.EMAIL.value,
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
