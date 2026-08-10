"""SQLAlchemy query adapter for tenant-scoped audit history."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEntry
from muxivo_console.infrastructure.persistence.models import AuditEventRecord


class SqlAlchemyAuditEntryReader:
    """Read only secret-free audit columns for one organization."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_organization(
        self,
        *,
        organization_id: UUID,
        after_event_id: UUID | None,
        actor_id: UUID | None,
        action: str | None,
        resource_type: str | None,
        result: str | None,
        limit: int,
    ) -> list[AuditEntry]:
        statement = select(AuditEventRecord).where(
            AuditEventRecord.organization_id == organization_id
        )
        if after_event_id is not None:
            cursor_created_at = (
                select(AuditEventRecord.created_at)
                .where(
                    AuditEventRecord.id == after_event_id,
                    AuditEventRecord.organization_id == organization_id,
                )
                .scalar_subquery()
            )
            statement = statement.where(
                or_(
                    AuditEventRecord.created_at < cursor_created_at,
                    and_(
                        AuditEventRecord.created_at == cursor_created_at,
                        AuditEventRecord.id < after_event_id,
                    ),
                )
            )
        if actor_id is not None:
            statement = statement.where(AuditEventRecord.actor_id == actor_id)
        if action is not None:
            statement = statement.where(AuditEventRecord.action == action)
        if resource_type is not None:
            statement = statement.where(AuditEventRecord.resource_type == resource_type)
        if result is not None:
            statement = statement.where(AuditEventRecord.result == result)
        statement = statement.order_by(
            AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc()
        ).limit(limit)

        async with self._session_factory() as session:
            records = (await session.execute(statement)).scalars().all()

        entries: list[AuditEntry] = []
        for record in records:
            if record.organization_id is None:
                continue
            try:
                entries.append(
                    AuditEntry(
                        id=record.id,
                        correlation_id=record.correlation_id,
                        actor_id=record.actor_id,
                        organization_id=record.organization_id,
                        action=record.action,
                        resource_type=record.resource_type,
                        resource_id=record.resource_id,
                        result=record.result,
                        created_at=record.created_at,
                    )
                )
            except ValueError:
                continue
        return entries
