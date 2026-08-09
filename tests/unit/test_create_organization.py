from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.create_organization import (
    CreateOrganization,
    CreateOrganizationCommand,
    OrganizationCreationRejectedError,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)


class SequenceIdentifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class UserStatuses:
    def __init__(self, status: UserStatus | None) -> None:
        self.status = status

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


class Slugs:
    def generate(self, organization_name: str) -> str:
        return "creator-community-01"


class OrganizationWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.organization: Organization | None = None
        self.owner_membership: OrganizationMembership | None = None
        self.audit_event: AuditEvent | None = None

    async def create(
        self,
        *,
        organization: Organization,
        owner_membership: OrganizationMembership,
        audit_event: AuditEvent,
    ) -> bool:
        self.organization = organization
        self.owner_membership = owner_membership
        self.audit_event = audit_event
        return self.result


def command(actor_id: UUID) -> CreateOrganizationCommand:
    return CreateOrganizationCommand(actor_id, "Creator community", uuid4())


@pytest.mark.asyncio
async def test_active_user_creates_organization_owner_membership_and_audit_event() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    membership_id = uuid4()
    audit_event_id = uuid4()
    writer = OrganizationWriter()
    use_case = CreateOrganization(
        SequenceIdentifiers([organization_id, membership_id, audit_event_id]),
        UserStatuses(UserStatus.ACTIVE),
        Slugs(),
        writer,
    )

    organization = await use_case.execute(command(actor_id))

    assert organization.id == organization_id
    assert organization.slug == "creator-community-01"
    assert writer.owner_membership == OrganizationMembership(
        actor_id=actor_id,
        organization_id=organization_id,
        role=OrganizationRole.OWNER,
        id=membership_id,
    )
    assert writer.audit_event.organization_id == organization_id
    assert writer.audit_event.action == "organization.create"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", (None, UserStatus.PENDING_VERIFICATION, UserStatus.SUSPENDED, UserStatus.DELETED)
)
async def test_non_active_user_cannot_create_an_organization(status: UserStatus | None) -> None:
    actor_id = uuid4()
    writer = OrganizationWriter()
    use_case = CreateOrganization(
        SequenceIdentifiers([uuid4(), uuid4(), uuid4()]), UserStatuses(status), Slugs(), writer
    )

    with pytest.raises(OrganizationCreationRejectedError):
        await use_case.execute(command(actor_id))

    assert writer.organization is None


@pytest.mark.asyncio
async def test_creation_conflict_does_not_yield_partial_result() -> None:
    actor_id = uuid4()
    writer = OrganizationWriter(result=False)
    use_case = CreateOrganization(
        SequenceIdentifiers([uuid4(), uuid4(), uuid4()]),
        UserStatuses(UserStatus.ACTIVE),
        Slugs(),
        writer,
    )

    with pytest.raises(OrganizationCreationRejectedError, match="could not be created"):
        await use_case.execute(command(actor_id))
