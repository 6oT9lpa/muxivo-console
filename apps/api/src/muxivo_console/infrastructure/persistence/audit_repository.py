"""Persistence adapter for standalone Console audit events."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
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
