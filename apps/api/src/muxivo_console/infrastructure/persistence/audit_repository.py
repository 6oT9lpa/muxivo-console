"""Persistence adapter for standalone Console audit events."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent, AuditLogEntry
from muxivo_console.infrastructure.persistence.models import AuditEventRecord


class SqlAlchemyAuditEventWriter:
    """Store audit facts emitted after resource-bound platform commands complete."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def record(self, event: AuditEvent) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    AuditEventRecord(
                        id=event.id,
                        correlation_id=event.correlation_id,
                        actor_id=event.actor_id,
                        organization_id=event.organization_id,
                        action=event.action,
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        result=event.result,
                    )
                )


class SqlAlchemyAuditEventReader:
    """Read only safe audit projections; command metadata is never returned to the browser."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_organization(
        self, *, organization_id, after_id, limit: int
    ) -> tuple[AuditLogEntry, ...]:
        statement = select(AuditEventRecord).where(
            AuditEventRecord.organization_id == organization_id
        )
        if after_id is not None:
            statement = statement.where(AuditEventRecord.id < after_id)
        statement = statement.order_by(AuditEventRecord.id.desc()).limit(limit)
        async with self._session_factory() as session:
            records = (await session.execute(statement)).scalars().all()
        return tuple(
            AuditLogEntry(
                id=record.id,
                correlation_id=record.correlation_id,
                actor_id=record.actor_id,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                result=record.result,
                created_at=record.created_at,
            )
            for record in records
        )
