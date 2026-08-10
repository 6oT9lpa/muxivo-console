from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.list_organization_members import ListOrganizationMembers
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.organizations import OrganizationMember, OrganizationRole


class Authorizer:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(self.allowed)


class MemberReader:
    def __init__(self, members: list[OrganizationMember]) -> None:
        self.members = members
        self.called = False
        self.arguments: dict[str, object] | None = None

    async def list_for_organization(
        self, *, organization_id: UUID, after_membership_id: UUID | None, limit: int
    ) -> list[OrganizationMember]:
        self.called = True
        self.arguments = {
            "organization_id": organization_id,
            "after_membership_id": after_membership_id,
            "limit": limit,
        }
        return self.members[:limit]


def member(role: OrganizationRole = OrganizationRole.VIEWER) -> OrganizationMember:
    return OrganizationMember(
        membership_id=uuid4(),
        user_id=uuid4(),
        display_name="Member",
        role=role,
    )


@pytest.mark.asyncio
async def test_member_listing_is_authorized_and_uses_keyset_pagination() -> None:
    organization_id = uuid4()
    cursor = uuid4()
    authorizer = Authorizer(True)
    members = [member(), member(), member()]
    reader = MemberReader(members)

    page = await ListOrganizationMembers(authorizer, reader).execute(
        actor_id=uuid4(),
        organization_id=organization_id,
        after_membership_id=cursor,
        limit=2,
    )

    assert page.items == tuple(members[:2])
    assert page.next_cursor == members[1].membership_id
    assert authorizer.request.resource is AuthorizationResource.ORGANIZATION_MEMBERSHIPS
    assert authorizer.request.action is AuthorizationAction.READ
    assert reader.arguments == {
        "organization_id": organization_id,
        "after_membership_id": cursor,
        "limit": 3,
    }


@pytest.mark.asyncio
async def test_member_listing_fails_closed_before_reading_when_unauthorized() -> None:
    reader = MemberReader([member()])
    use_case = ListOrganizationMembers(Authorizer(False), reader)

    with pytest.raises(AccessDeniedError):
        await use_case.execute(actor_id=uuid4(), organization_id=uuid4())

    assert reader.called is False
