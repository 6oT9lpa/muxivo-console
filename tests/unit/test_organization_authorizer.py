from uuid import UUID, uuid4

import pytest
from muxivo_console.application.organization_authorizer import MembershipOrganizationAuthorizer
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    OrganizationMembership,
    OrganizationRole,
)


class StubMembershipReader:
    def __init__(self, membership: OrganizationMembership | None) -> None:
        self.membership = membership
        self.requested_actor_id: UUID | None = None
        self.requested_organization_id: UUID | None = None

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None:
        self.requested_actor_id = actor_id
        self.requested_organization_id = organization_id
        return self.membership


def control_module_read(actor_id: UUID, organization_id: UUID) -> AuthorizationRequest:
    return AuthorizationRequest(
        actor_id=actor_id,
        organization_id=organization_id,
        resource=AuthorizationResource.CONTROL_MODULES,
        action=AuthorizationAction.READ,
    )


@pytest.mark.asyncio
async def test_owner_can_read_organization_control_modules_without_a_scope() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    reader = StubMembershipReader(
        OrganizationMembership(actor_id, organization_id, OrganizationRole.OWNER)
    )

    decision = await MembershipOrganizationAuthorizer(reader).authorize(
        control_module_read(actor_id, organization_id)
    )

    assert decision.allowed is True
    assert reader.requested_actor_id == actor_id
    assert reader.requested_organization_id == organization_id


@pytest.mark.asyncio
async def test_non_owner_requires_an_explicit_resource_scope() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    membership = OrganizationMembership(actor_id, organization_id, OrganizationRole.MODERATOR)
    authorizer = MembershipOrganizationAuthorizer(StubMembershipReader(membership))

    decision = await authorizer.authorize(control_module_read(actor_id, organization_id))

    assert decision.allowed is False


@pytest.mark.asyncio
async def test_explicit_scope_allows_only_its_resource_and_action() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    membership = OrganizationMembership(
        actor_id,
        organization_id,
        OrganizationRole.MODERATOR,
        frozenset(
            {
                MembershipResourceScope(
                    AuthorizationResource.CONTROL_MODULES, AuthorizationAction.READ
                )
            }
        ),
    )
    authorizer = MembershipOrganizationAuthorizer(StubMembershipReader(membership))

    allowed = await authorizer.authorize(control_module_read(actor_id, organization_id))
    denied = await authorizer.authorize(
        AuthorizationRequest(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.MANAGE,
        )
    )

    assert allowed.allowed is True
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_missing_membership_is_denied() -> None:
    actor_id = uuid4()
    organization_id = uuid4()

    decision = await MembershipOrganizationAuthorizer(StubMembershipReader(None)).authorize(
        control_module_read(actor_id, organization_id)
    )

    assert decision.allowed is False


def test_role_assignment_may_not_grant_equal_or_greater_privilege() -> None:
    assert OrganizationRole.OWNER.may_assign(OrganizationRole.ADMIN) is True
    assert OrganizationRole.ADMIN.may_assign(OrganizationRole.MODERATOR) is True
    assert OrganizationRole.ADMIN.may_assign(OrganizationRole.ADMIN) is False
    assert OrganizationRole.MODERATOR.may_assign(OrganizationRole.ADMIN) is False


def test_admin_can_manage_platform_connections_only_with_an_explicit_scope() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    request = AuthorizationRequest(
        actor_id=actor_id,
        organization_id=organization_id,
        resource=AuthorizationResource.PLATFORM_CONNECTIONS,
        action=AuthorizationAction.MANAGE,
    )
    without_scope = OrganizationMembership(actor_id, organization_id, OrganizationRole.ADMIN)
    with_scope = OrganizationMembership(
        actor_id,
        organization_id,
        OrganizationRole.ADMIN,
        frozenset(
            {
                MembershipResourceScope(
                    AuthorizationResource.PLATFORM_CONNECTIONS, AuthorizationAction.MANAGE
                )
            }
        ),
    )

    assert without_scope.allows(request) is False
    assert with_scope.allows(request) is True


def test_owner_can_manage_platform_connections_without_an_explicit_scope() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    request = AuthorizationRequest(
        actor_id=actor_id,
        organization_id=organization_id,
        resource=AuthorizationResource.PLATFORM_CONNECTIONS,
        action=AuthorizationAction.MANAGE,
    )

    owner = OrganizationMembership(actor_id, organization_id, OrganizationRole.OWNER)

    assert owner.allows(request) is True
