"""Atomic persistence for one-time OAuth login state and its audit fact."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.oauth_login import OAuthLoginTransaction
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    OAuthLoginTransactionRecord,
)


class SqlAlchemyOAuthLoginTransactionWriter:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(self, *, transaction: OAuthLoginTransaction, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all((
                        OAuthLoginTransactionRecord(
                            id=transaction.id, provider=transaction.provider.value,
                            state_hash=transaction.state_hash,
                            code_verifier_ciphertext=transaction.code_verifier_ciphertext,
                            expires_at=transaction.expires_at,
                        ),
                        AuditEventRecord(
                            id=audit_event.id, correlation_id=audit_event.correlation_id,
                            actor_id=audit_event.actor_id,
                            organization_id=audit_event.organization_id,
                            action=audit_event.action, resource_type=audit_event.resource_type,
                            resource_id=audit_event.resource_id, result=audit_event.result,
                        ),
                    ))
        except IntegrityError:
            return False
        return True


class SqlAlchemyOAuthLoginTransactionConsumer:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def consume(
        self, *, state_hash: str, consumed_at: datetime
    ) -> OAuthLoginTransaction | None:
        statement = update(OAuthLoginTransactionRecord).where(
            OAuthLoginTransactionRecord.state_hash == state_hash,
            OAuthLoginTransactionRecord.consumed_at.is_(None),
            OAuthLoginTransactionRecord.expires_at > consumed_at,
        ).values(consumed_at=consumed_at).returning(OAuthLoginTransactionRecord)
        async with self._session_factory() as session:
            async with session.begin():
                record = (await session.execute(statement)).scalar_one_or_none()
        if record is None:
            return None
        return OAuthLoginTransaction(
            record.id, LoginIdentityProvider(record.provider), record.state_hash,
            record.code_verifier_ciphertext, record.expires_at,
        )
