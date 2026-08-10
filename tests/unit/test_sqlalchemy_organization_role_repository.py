from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace, TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organizations import OrganizationRole
from muxivo_console.infrastructure.persistence.models import AuditEventRecord
from muxivo_console.infrastructure.persistence.organization_role_repository import (
    SqlAlchemyOrganizationMemberRoleWriter,
)


class FakeResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class Transaction(AbstractAsyncContextManager[Self]):
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, actor, target) -> None:
        self.results = [FakeResult(actor), FakeResult(target)]
        self.statements = []
        self.added = []
        self.flushed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> Transaction:
        return Transaction()

    async def execute(self, statement) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_role_writer_rechecks_locked_actor_and_target_before_auditing() -> None:
    organization_id = uuid4()
    actor_id = uuid4()
    actor = SimpleNamespace(role="owner")
    target = SimpleNamespace(role="admin")
    session = FakeSession(actor, target)
    audit = AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=actor_id,
        organization_id=organization_id,
        action="organization.membership_role_changed",
        resource_type="organization_membership",
        resource_id=str(uuid4()),
        result="succeeded",
    )

    changed = await SqlAlchemyOrganizationMemberRoleWriter(lambda: session).change_role(
        organization_id=organization_id,
        actor_membership_id=uuid4(),
        actor_id=actor_id,
        expected_actor_role=OrganizationRole.OWNER,
        membership_id=uuid4(),
        target_user_id=uuid4(),
        expected_role=OrganizationRole.ADMIN,
        new_role=OrganizationRole.VIEWER,
        audit_event=audit,
    )

    assert changed is True
    assert target.role == "viewer"
    assert session.flushed is True
    assert len(session.added) == 1
    assert isinstance(session.added[0], AuditEventRecord)
    assert all("FOR UPDATE" in str(statement) for statement in session.statements)


@pytest.mark.asyncio
async def test_role_writer_fails_closed_when_actor_role_changed() -> None:
    session = FakeSession(SimpleNamespace(role="admin"), SimpleNamespace(role="viewer"))

    changed = await SqlAlchemyOrganizationMemberRoleWriter(lambda: session).change_role(
        organization_id=uuid4(),
        actor_membership_id=uuid4(),
        actor_id=uuid4(),
        expected_actor_role=OrganizationRole.OWNER,
        membership_id=uuid4(),
        target_user_id=uuid4(),
        expected_role=OrganizationRole.VIEWER,
        new_role=OrganizationRole.ANALYST,
        audit_event=AuditEvent(
            id=uuid4(),
            correlation_id=uuid4(),
            actor_id=uuid4(),
            organization_id=uuid4(),
            action="organization.membership_role_changed",
            resource_type="organization_membership",
            resource_id=str(uuid4()),
            result="succeeded",
        ),
    )

    assert changed is False
    assert session.added == []
    assert session.flushed is False
    assert len(session.statements) == 1
