from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    OrganizationMembershipRecord,
    OrganizationRecord,
)
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationCreationWriter,
    SqlAlchemyUserStatusReader,
)
from sqlalchemy.exc import IntegrityError


@dataclass
class FakeTransaction(AbstractAsyncContextManager[None]):
    exc_type: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.exc_type = exc_type
        return False


class FakeResult:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> str | None:
        return self.value


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, *, status: str | None = None, integrity_error: bool = False) -> None:
        self.status = status
        self.integrity_error = integrity_error
        self.records: tuple[object, ...] = ()
        self.transaction = FakeTransaction()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return self.transaction

    async def execute(self, statement) -> FakeResult:
        return FakeResult(self.status)

    def add_all(self, records: tuple[object, ...]) -> None:
        self.records = records

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))


def owner_membership(actor_id: UUID, organization_id: UUID) -> OrganizationMembership:
    return OrganizationMembership(
        actor_id=actor_id,
        organization_id=organization_id,
        role=OrganizationRole.OWNER,
        id=uuid4(),
    )


def audit_event(actor_id: UUID, organization_id: UUID) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=actor_id,
        organization_id=organization_id,
        action="organization.create",
        resource_type="organization",
        resource_id=str(organization_id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_reads_only_known_user_statuses() -> None:
    active_session = FakeSession(status="active")
    invalid_session = FakeSession(status="unexpected")

    assert (
        await SqlAlchemyUserStatusReader(lambda: active_session).get_status(user_id=uuid4())
        is UserStatus.ACTIVE
    )
    assert (
        await SqlAlchemyUserStatusReader(lambda: invalid_session).get_status(user_id=uuid4())
        is None
    )


@pytest.mark.asyncio
async def test_writes_organization_owner_and_audit_event_in_one_transaction() -> None:
    session = FakeSession()
    actor_id = uuid4()
    organization = Organization(uuid4(), "Creator community", "creator-community-01")

    created = await SqlAlchemyOrganizationCreationWriter(lambda: session).create(
        organization=organization,
        owner_membership=owner_membership(actor_id, organization.id),
        audit_event=audit_event(actor_id, organization.id),
    )

    assert created is True
    assert session.transaction.exc_type is None
    assert tuple(type(record) for record in session.records) == (
        OrganizationRecord,
        OrganizationMembershipRecord,
        AuditEventRecord,
    )


@pytest.mark.asyncio
async def test_duplicate_organization_write_is_reduced_to_a_safe_failure() -> None:
    session = FakeSession(integrity_error=True)
    actor_id = uuid4()
    organization = Organization(uuid4(), "Creator community", "creator-community-01")

    created = await SqlAlchemyOrganizationCreationWriter(lambda: session).create(
        organization=organization,
        owner_membership=owner_membership(actor_id, organization.id),
        audit_event=audit_event(actor_id, organization.id),
    )

    assert created is False
    assert session.transaction.exc_type is IntegrityError
