from uuid import uuid4

import pytest
from muxivo_console.application.list_organizations import ListOrganizations
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationAccess,
    OrganizationRole,
)


class OrganizationReader:
    def __init__(self, items: list[OrganizationAccess]) -> None:
        self.items = items
        self.arguments = None

    async def list_for_actor(self, **kwargs) -> list[OrganizationAccess]:
        self.arguments = kwargs
        return self.items


def access(name: str, role: OrganizationRole = OrganizationRole.OWNER) -> OrganizationAccess:
    return OrganizationAccess(
        organization=Organization(id=uuid4(), name=name, slug=name.lower()),
        role=role,
    )


@pytest.mark.asyncio
async def test_list_organizations_uses_keyset_page_and_membership_boundary() -> None:
    actor_id = uuid4()
    cursor = uuid4()
    first = access("First")
    second = access("Second", OrganizationRole.ADMIN)
    third = access("Third")
    reader = OrganizationReader([first, second, third])

    page = await ListOrganizations(reader).execute(
        actor_id=actor_id,
        after_organization_id=cursor,
        limit=2,
    )

    assert page.items == (first, second)
    assert page.next_cursor == second.organization.id
    assert reader.arguments == {
        "actor_id": actor_id,
        "after_organization_id": cursor,
        "limit": 3,
    }


@pytest.mark.asyncio
async def test_list_organizations_rejects_unbounded_page_sizes() -> None:
    with pytest.raises(ValueError):
        await ListOrganizations(OrganizationReader([])).execute(
            actor_id=uuid4(),
            limit=101,
        )
