"""Persistence adapter for Console-owned, non-secret platform connection metadata."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    PlatformConnectionRecord,
)


class SqlAlchemyPlatformConnectionWriter:
    """Persist connection metadata and its audit event atomically; never credentials."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(self, *, connection: PlatformConnection, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(
                        (
                            PlatformConnectionRecord(
                                id=connection.id,
                                organization_id=connection.organization_id,
                                platform=connection.platform.value,
                                external_resource_id=connection.external_resource_id,
                                status=connection.status.value,
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


class SqlAlchemyPlatformConnectionReader:
    """Read non-secret connection records in stable UUIDv7 keyset order."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_organization(
        self, *, organization_id: UUID, after_id: UUID | None, limit: int
    ) -> tuple[PlatformConnection, ...]:
        statement = (
            select(PlatformConnectionRecord)
            .where(PlatformConnectionRecord.organization_id == organization_id)
            .order_by(PlatformConnectionRecord.id)
            .limit(limit)
        )
        if after_id is not None:
            statement = statement.where(PlatformConnectionRecord.id > after_id)
        async with self._session_factory() as session:
            result = await session.execute(statement)
            records = result.scalars().all()
        connections: list[PlatformConnection] = []
        for record in records:
            try:
                connections.append(
                    PlatformConnection(
                        id=record.id,
                        organization_id=record.organization_id,
                        platform=Platform(record.platform),
                        external_resource_id=record.external_resource_id,
                        status=ConnectionStatus(record.status),
                    )
                )
            except ValueError:
                continue
        return tuple(connections)
