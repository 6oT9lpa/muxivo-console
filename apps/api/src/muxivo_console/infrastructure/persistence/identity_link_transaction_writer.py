"""Transactional persistence of OAuth state and PKCE verifier ciphertext."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider
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


class SqlAlchemyIdentityLinkTransactionConsumer:
    """Claim a valid state in one SQL statement to reject concurrent/replayed callbacks."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def consume(
        self, *, state_hash: str, consumed_at: datetime
    ) -> IdentityLinkTransaction | None:
        statement = (
            update(IdentityLinkTransactionRecord)
            .where(
                IdentityLinkTransactionRecord.state_hash == state_hash,
                IdentityLinkTransactionRecord.consumed_at.is_(None),
                IdentityLinkTransactionRecord.expires_at > consumed_at,
            )
            .values(consumed_at=consumed_at)
            .returning(IdentityLinkTransactionRecord)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
                record = result.scalar_one_or_none()
        if record is None:
            return None
        try:
            return IdentityLinkTransaction(
                id=record.id,
                user_id=record.user_id,
                provider=LoginIdentityProvider(record.provider),
                state_hash=record.state_hash,
                code_verifier_ciphertext=record.code_verifier_ciphertext,
                expires_at=record.expires_at,
                consumed_at=record.consumed_at,
            )
        except ValueError:
            return None
