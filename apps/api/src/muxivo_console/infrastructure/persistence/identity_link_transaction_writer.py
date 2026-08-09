"""Transactional persistence of OAuth state and PKCE verifier ciphertext."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity_linking import IdentityLinkTransaction
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    IdentityLinkTransactionRecord,
)


class SqlAlchemyIdentityLinkTransactionWriter:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(
        self, *, transaction: IdentityLinkTransaction, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(
                        (
                            IdentityLinkTransactionRecord(
                                id=transaction.id,
                                user_id=transaction.user_id,
                                provider=transaction.provider.value,
                                state_hash=transaction.state_hash,
                                code_verifier_ciphertext=transaction.code_verifier_ciphertext,
                                expires_at=transaction.expires_at,
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
