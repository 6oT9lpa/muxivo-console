from uuid import UUID, uuid4

import pytest
from muxivo_console.application.change_organization_member_role import (
    ChangeOrganizationMemberRole,
    ChangeOrganizationMemberRoleCommand,
    OrganizationMemberNotFoundError,
    OrganizationRoleChangeConflictError,
    OrganizationRoleChangeRejectedError,
)
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.organizations import (
    OrganizationMember,
    OrganizationMembership,
    OrganizationRole,
)


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(self.allowed)


class Memberships:
    def __init__(self, membership: OrganizationMembership | None) -> None:
        self.membership = membership

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None:
        return self.membership


class Members:
    def __init__(self, member: OrganizationMember | None) -> None:
        self.member = member

    async def find_for_organization(
        self, *, organization_id: UUID, membership_id: UUID
    ) -> OrganizationMember | None:
        if self.member is not None and self.member.membership_id == membership_id:
            return self.member
        return None


class Roles:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.arguments: dict[str, object] | None = None

    async def change_role(self, **arguments) -> bool:
        self.arguments = arguments
        return self.result


class Identifiers:
    def __init__(self) -> None:
        self.value = uuid4()

    def new(self) -> UUID:
        return self.value


def actor_membership(role: OrganizationRole, organization_id: UUID) -> OrganizationMembership:
    return OrganizationMembership(
        id=uuid4(),
        actor_id=uuid4(),
        organization_id=organization_id,
        role=role,
    )


def target(role: OrganizationRole) -> OrganizationMember:
    return OrganizationMember(uuid4(), uuid4(), "Target", role)


def command(
    *, actor_id: UUID, organization_id: UUID, membership_id: UUID, role: OrganizationRole
) -> ChangeOrganizationMemberRoleCommand:
    return ChangeOrganizationMemberRoleCommand(
        actor_id=actor_id,
        organization_id=organization_id,
        membership_id=membership_id,
        role=role,
        correlation_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_owner_can_change_admin_to_viewer_with_atomic_audit() -> None:
    organization_id = uuid4()
    actor = actor_membership(OrganizationRole.OWNER, organization_id)
    member = target(OrganizationRole.ADMIN)
    roles = Roles()
    use_case = ChangeOrganizationMemberRole(
        Authorizer(), Memberships(actor), Members(member), roles, Identifiers()
    )

    result = await use_case.execute(
        command(
            actor_id=actor.actor_id,
            organization_id=organization_id,
            membership_id=member.membership_id,
            role=OrganizationRole.VIEWER,
        )
    )

    assert result.role is OrganizationRole.VIEWER
    assert roles.arguments["expected_actor_role"] is OrganizationRole.OWNER
    assert roles.arguments["expected_role"] is OrganizationRole.ADMIN
    assert roles.arguments["new_role"] is OrganizationRole.VIEWER
    audit = roles.arguments["audit_event"]
    assert audit.action == "organization.membership_role_changed"
    assert audit.organization_id == organization_id
    assert audit.resource_id == str(member.membership_id)


@pytest.mark.asyncio
async def test_admin_cannot_modify_another_admin() -> None:
    organization_id = uuid4()
    actor = actor_membership(OrganizationRole.ADMIN, organization_id)
    member = target(OrganizationRole.ADMIN)
    roles = Roles()
    use_case = ChangeOrganizationMemberRole(
        Authorizer(), Memberships(actor), Members(member), roles, Identifiers()
    )

    with pytest.raises(OrganizationRoleChangeRejectedError):
        await use_case.execute(
            command(
                actor_id=actor.actor_id,
                organization_id=organization_id,
                membership_id=member.membership_id,
                role=OrganizationRole.VIEWER,
            )
        )

    assert roles.arguments is None


@pytest.mark.asyncio
async def test_owner_role_is_immutable_in_generic_role_change_flow() -> None:
    organization_id = uuid4()
    actor = actor_membership(OrganizationRole.OWNER, organization_id)
    member = target(OrganizationRole.ADMIN)
    use_case = ChangeOrganizationMemberRole(
        Authorizer(), Memberships(actor), Members(member), Roles(), Identifiers()
    )

    with pytest.raises(OrganizationRoleChangeRejectedError, match="ownership-transfer"):
        await use_case.execute(
            command(
                actor_id=actor.actor_id,
                organization_id=organization_id,
                membership_id=member.membership_id,
                role=OrganizationRole.OWNER,
            )
        )


@pytest.mark.asyncio
async def test_unauthorized_actor_fails_before_membership_lookup() -> None:
    organization_id = uuid4()
    use_case = ChangeOrganizationMemberRole(
        Authorizer(False), Memberships(None), Members(None), Roles(), Identifiers()
    )

    with pytest.raises(AccessDeniedError):
        await use_case.execute(
            command(
                actor_id=uuid4(),
                organization_id=organization_id,
                membership_id=uuid4(),
                role=OrganizationRole.VIEWER,
            )
        )


@pytest.mark.asyncio
async def test_missing_target_is_not_conflated_with_concurrent_conflict() -> None:
    organization_id = uuid4()
    actor = actor_membership(OrganizationRole.OWNER, organization_id)
    use_case = ChangeOrganizationMemberRole(
        Authorizer(), Memberships(actor), Members(None), Roles(), Identifiers()
    )

    with pytest.raises(OrganizationMemberNotFoundError):
        await use_case.execute(
            command(
                actor_id=actor.actor_id,
                organization_id=organization_id,
                membership_id=uuid4(),
                role=OrganizationRole.VIEWER,
            )
        )


@pytest.mark.asyncio
async def test_concurrent_membership_change_fails_closed() -> None:
    organization_id = uuid4()
    actor = actor_membership(OrganizationRole.OWNER, organization_id)
    member = target(OrganizationRole.ADMIN)
    use_case = ChangeOrganizationMemberRole(
        Authorizer(), Memberships(actor), Members(member), Roles(False), Identifiers()
    )

    with pytest.raises(OrganizationRoleChangeConflictError):
        await use_case.execute(
            command(
                actor_id=actor.actor_id,
                organization_id=organization_id,
                membership_id=member.membership_id,
                role=OrganizationRole.VIEWER,
            )
        )
