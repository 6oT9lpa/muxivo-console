"""Transactional persistence for provider-verified identity links."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentity
from muxivo_console.infrastructure.persistence.models import AuditEventRecord, LoginIdentityRecord


class SqlAlchemyLoginIdentityLinkWriter:
    """Store a link atomically; uniqueness prevents cross-account identity takeover."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def link(self, *, identity: LoginIdentity, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(
                        (
                            LoginIdentityRecord(
                                id=identity.id,
                                user_id=identity.user_id,
                                provider=identity.provider.value,
                                provider_subject=identity.provider_subject,
                            ),
                            AuditEventRecord(
                                id=audit_event.id,
                                correlation_id=audit_event.correlation_id,
                                actor_id=audit_event.actor_id,
                                organization_id=None,
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
