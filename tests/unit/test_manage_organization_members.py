from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.manage_organization_members import (
    AddOrganizationMember,
    AddOrganizationMemberCommand,
    OrganizationMemberManagementRejectedError,
    RemoveOrganizationMember,
    RemoveOrganizationMemberCommand,
    UpdateOrganizationMember,
    UpdateOrganizationMemberCommand,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    OrganizationMembership,
    OrganizationRole,
)


class SequenceIdentifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class UserStatuses:
    def __init__(self, statuses: dict[UUID, UserStatus | None]) -> None:
        self.statuses = statuses

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.statuses.get(user_id)


class EmailNormalizer:
    def normalize(self, value: str) -> str:
        return value.strip().lower()


class EmailLookupHasher:
    def lookup_hash(self, normalized_email: str) -> str:
        return f"lookup:{normalized_email}"


class Invitees:
    def __init__(self, users: dict[str, UUID | None]) -> None:
        self.users = users
        self.lookup_hash: str | None = None

    async def find_active_user_id_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> UUID | None:
        self.lookup_hash = email_lookup_hash
        return self.users.get(email_lookup_hash)


class Memberships:
    def __init__(self, memberships: dict[tuple[UUID, UUID], OrganizationMembership]) -> None:
        self.memberships = memberships

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None:
        return self.memberships.get((actor_id, organization_id))


class MemberWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.membership: OrganizationMembership | None = None
        self.audit_event: AuditEvent | None = None
        self.removed_membership_id: UUID | None = None

    async def add_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool:
        self.membership = membership
        self.audit_event = audit_event
        return self.result

    async def update_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool:
        self.membership = membership
        self.audit_event = audit_event
        return self.result

    async def remove_member(self, *, membership_id: UUID, audit_event: AuditEvent) -> bool:
        self.removed_membership_id = membership_id
        self.audit_event = audit_event
        return self.result


def membership(
    user_id: UUID,
    organization_id: UUID,
    role: OrganizationRole,
    *,
    membership_id: UUID | None = None,
) -> OrganizationMembership:
    return OrganizationMembership(
        id=membership_id or uuid4(),
        actor_id=user_id,
        organization_id=organization_id,
        role=role,
    )


def control_read_scope() -> MembershipResourceScope:
    return MembershipResourceScope(
        resource=AuthorizationResource.CONTROL_MODULES,
        action=AuthorizationAction.READ,
    )


def platform_manage_scope() -> MembershipResourceScope:
    return MembershipResourceScope(
        resource=AuthorizationResource.PLATFORM_CONNECTIONS,
        action=AuthorizationAction.MANAGE,
    )


@pytest.mark.asyncio
async def test_owner_adds_lower_role_with_scopes_and_audit_event() -> None:
    owner_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    membership_id = uuid4()
    scope_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    writer = MemberWriter()
    use_case = AddOrganizationMember(
        identifiers=SequenceIdentifiers([membership_id, scope_id, audit_id]),
        email_normalizer=EmailNormalizer(),
        email_lookup_hasher=EmailLookupHasher(),
        invitees=Invitees({"lookup:creator@example.com": target_id}),
        user_statuses=UserStatuses({target_id: UserStatus.ACTIVE}),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                )
            }
        ),
        members=writer,
    )

    created = await use_case.execute(
        AddOrganizationMemberCommand(
            actor_id=owner_id,
            organization_id=organization_id,
            email=" Creator@Example.com ",
            role=OrganizationRole.VIEWER,
            resource_scopes=(control_read_scope(),),
            correlation_id=correlation_id,
        )
    )

    assert created.id == membership_id
    assert created.actor_id == target_id
    assert created.resource_scopes == frozenset(
        (
            MembershipResourceScope(
                id=scope_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
            ),
        )
    )
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "organization.member.add"
    assert writer.audit_event.resource_id == str(target_id)
    assert writer.audit_event.correlation_id == correlation_id


@pytest.mark.asyncio
async def test_admin_cannot_assign_equal_or_higher_role() -> None:
    admin_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    use_case = AddOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        email_normalizer=EmailNormalizer(),
        email_lookup_hasher=EmailLookupHasher(),
        invitees=Invitees({"lookup:admin@example.com": target_id}),
        user_statuses=UserStatuses({target_id: UserStatus.ACTIVE}),
        memberships=Memberships(
            {
                (admin_id, organization_id): membership(
                    admin_id, organization_id, OrganizationRole.ADMIN
                )
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            AddOrganizationMemberCommand(
                actor_id=admin_id,
                organization_id=organization_id,
                email="admin@example.com",
                role=OrganizationRole.ADMIN,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None


@pytest.mark.asyncio
async def test_moderator_cannot_add_a_lower_role_member() -> None:
    moderator_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    use_case = AddOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        email_normalizer=EmailNormalizer(),
        email_lookup_hasher=EmailLookupHasher(),
        invitees=Invitees({"lookup:viewer@example.com": target_id}),
        user_statuses=UserStatuses({target_id: UserStatus.ACTIVE}),
        memberships=Memberships(
            {
                (moderator_id, organization_id): membership(
                    moderator_id, organization_id, OrganizationRole.MODERATOR
                )
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            AddOrganizationMemberCommand(
                actor_id=moderator_id,
                organization_id=organization_id,
                email="viewer@example.com",
                role=OrganizationRole.VIEWER,
                resource_scopes=(control_read_scope(),),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None


@pytest.mark.asyncio
async def test_member_invite_rejects_scope_that_target_role_cannot_use() -> None:
    owner_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    use_case = AddOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4(), uuid4(), uuid4()]),
        email_normalizer=EmailNormalizer(),
        email_lookup_hasher=EmailLookupHasher(),
        invitees=Invitees({"lookup:viewer@example.com": target_id}),
        user_statuses=UserStatuses({target_id: UserStatus.ACTIVE}),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                )
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            AddOrganizationMemberCommand(
                actor_id=owner_id,
                organization_id=organization_id,
                email="viewer@example.com",
                role=OrganizationRole.VIEWER,
                resource_scopes=(platform_manage_scope(),),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_member_invite_by_email_rejects_unknown_active_user() -> None:
    owner_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    invitees = Invitees({})
    use_case = AddOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        email_normalizer=EmailNormalizer(),
        email_lookup_hasher=EmailLookupHasher(),
        invitees=invitees,
        user_statuses=UserStatuses({}),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                )
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            AddOrganizationMemberCommand(
                actor_id=owner_id,
                organization_id=organization_id,
                email="missing@example.com",
                role=OrganizationRole.VIEWER,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert invitees.lookup_hash == "lookup:missing@example.com"
    assert writer.membership is None


@pytest.mark.asyncio
async def test_member_update_denies_self_change() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    use_case = UpdateOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4()]),
        memberships=Memberships(
            {
                (actor_id, organization_id): membership(
                    actor_id, organization_id, OrganizationRole.OWNER
                )
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            UpdateOrganizationMemberCommand(
                actor_id=actor_id,
                organization_id=organization_id,
                user_id=actor_id,
                role=OrganizationRole.ADMIN,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None


@pytest.mark.asyncio
async def test_moderator_cannot_update_a_lower_role_member() -> None:
    moderator_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    writer = MemberWriter()
    use_case = UpdateOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4()]),
        memberships=Memberships(
            {
                (moderator_id, organization_id): membership(
                    moderator_id, organization_id, OrganizationRole.MODERATOR
                ),
                (target_id, organization_id): membership(
                    target_id, organization_id, OrganizationRole.VIEWER
                ),
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            UpdateOrganizationMemberCommand(
                actor_id=moderator_id,
                organization_id=organization_id,
                user_id=target_id,
                role=OrganizationRole.VIEWER,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None


@pytest.mark.asyncio
async def test_owner_updates_lower_role_member_with_scopes_and_audit_event() -> None:
    owner_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    target_membership_id = uuid4()
    scope_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    writer = MemberWriter()
    use_case = UpdateOrganizationMember(
        identifiers=SequenceIdentifiers([scope_id, audit_id]),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                ),
                (target_id, organization_id): membership(
                    target_id,
                    organization_id,
                    OrganizationRole.VIEWER,
                    membership_id=target_membership_id,
                ),
            }
        ),
        members=writer,
    )

    updated = await use_case.execute(
        UpdateOrganizationMemberCommand(
            actor_id=owner_id,
            organization_id=organization_id,
            user_id=target_id,
            role=OrganizationRole.MODERATOR,
            resource_scopes=(control_read_scope(),),
            correlation_id=correlation_id,
        )
    )

    assert updated.id == target_membership_id
    assert updated.actor_id == target_id
    assert updated.role is OrganizationRole.MODERATOR
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "organization.member.update"
    assert writer.audit_event.resource_id == str(target_id)
    assert writer.audit_event.correlation_id == correlation_id


@pytest.mark.asyncio
async def test_member_update_rejects_scope_that_target_role_cannot_use() -> None:
    owner_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    target_membership_id = uuid4()
    writer = MemberWriter()
    use_case = UpdateOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                ),
                (target_id, organization_id): membership(
                    target_id,
                    organization_id,
                    OrganizationRole.VIEWER,
                    membership_id=target_membership_id,
                ),
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            UpdateOrganizationMemberCommand(
                actor_id=owner_id,
                organization_id=organization_id,
                user_id=target_id,
                role=OrganizationRole.ANALYST,
                resource_scopes=(platform_manage_scope(),),
                correlation_id=uuid4(),
            )
        )

    assert writer.membership is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_admin_cannot_remove_equal_role_member() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    target_membership_id = uuid4()
    writer = MemberWriter()
    use_case = RemoveOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4()]),
        memberships=Memberships(
            {
                (actor_id, organization_id): membership(
                    actor_id, organization_id, OrganizationRole.ADMIN
                ),
                (target_id, organization_id): membership(
                    target_id,
                    organization_id,
                    OrganizationRole.ADMIN,
                    membership_id=target_membership_id,
                ),
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            RemoveOrganizationMemberCommand(
                actor_id=actor_id,
                organization_id=organization_id,
                user_id=target_id,
                correlation_id=uuid4(),
            )
        )

    assert writer.removed_membership_id is None


@pytest.mark.asyncio
async def test_moderator_cannot_remove_a_lower_role_member() -> None:
    moderator_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    target_membership_id = uuid4()
    writer = MemberWriter()
    use_case = RemoveOrganizationMember(
        identifiers=SequenceIdentifiers([uuid4()]),
        memberships=Memberships(
            {
                (moderator_id, organization_id): membership(
                    moderator_id, organization_id, OrganizationRole.MODERATOR
                ),
                (target_id, organization_id): membership(
                    target_id,
                    organization_id,
                    OrganizationRole.VIEWER,
                    membership_id=target_membership_id,
                ),
            }
        ),
        members=writer,
    )

    with pytest.raises(OrganizationMemberManagementRejectedError):
        await use_case.execute(
            RemoveOrganizationMemberCommand(
                actor_id=moderator_id,
                organization_id=organization_id,
                user_id=target_id,
                correlation_id=uuid4(),
            )
        )

    assert writer.removed_membership_id is None


@pytest.mark.asyncio
async def test_owner_removes_lower_role_member_with_audit_event() -> None:
    owner_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    target_membership_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    writer = MemberWriter()
    use_case = RemoveOrganizationMember(
        identifiers=SequenceIdentifiers([audit_id]),
        memberships=Memberships(
            {
                (owner_id, organization_id): membership(
                    owner_id, organization_id, OrganizationRole.OWNER
                ),
                (target_id, organization_id): membership(
                    target_id,
                    organization_id,
                    OrganizationRole.VIEWER,
                    membership_id=target_membership_id,
                ),
            }
        ),
        members=writer,
    )

    await use_case.execute(
        RemoveOrganizationMemberCommand(
            actor_id=owner_id,
            organization_id=organization_id,
            user_id=target_id,
            correlation_id=correlation_id,
        )
    )

    assert writer.removed_membership_id == target_membership_id
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "organization.member.remove"
    assert writer.audit_event.resource_id == str(target_id)
    assert writer.audit_event.correlation_id == correlation_id
