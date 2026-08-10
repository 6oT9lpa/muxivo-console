from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_audit_events import ListAuditEvents
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.domain.audit import AuditEntry
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest


class Authorizer:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(allowed=self.allowed)


class Reader:
    def __init__(self, entries: list[AuditEntry]) -> None:
        self.entries = entries
        self.arguments = None

    async def list_for_organization(self, **arguments) -> list[AuditEntry]:
        self.arguments = arguments
        return self.entries


def entry(identifier: UUID) -> AuditEntry:
    return AuditEntry(
        id=identifier,
        correlation_id=uuid4(),
        actor_id=uuid4(),
        organization_id=uuid4(),
        action="organization.member.role_changed",
        resource_type="organization_membership",
        resource_id=str(uuid4()),
        result="succeeded",
        created_at=datetime(2026, 8, 10, 18, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_lists_authorized_tenant_events_with_keyset_pagination_and_filters() -> None:
    organization_id = uuid4()
    actor_id = uuid4()
    filtered_actor_id = uuid4()
    first, second, extra = entry(uuid4()), entry(uuid4()), entry(uuid4())
    reader = Reader([first, second, extra])
    authorizer = Authorizer(True)
    use_case = ListAuditEvents(authorizer, reader)

    page = await use_case.execute(
        actor_id=actor_id,
        organization_id=organization_id,
        filter_actor_id=filtered_actor_id,
        action="organization.member.role_changed",
        result="succeeded",
        limit=2,
    )

    assert page.items == (first, second)
    assert page.next_cursor == second.id
    assert reader.arguments == {
        "organization_id": organization_id,
        "after_event_id": None,
        "actor_id": filtered_actor_id,
        "action": "organization.member.role_changed",
        "resource_type": None,
        "result": "succeeded",
        "limit": 3,
    }
    assert authorizer.request.organization_id == organization_id
    assert authorizer.request.resource.value == "console.audit_events"
    assert authorizer.request.action.value == "read"


@pytest.mark.asyncio
async def test_denies_before_querying_audit_storage() -> None:
    reader = Reader([])
    use_case = ListAuditEvents(Authorizer(False), reader)

    with pytest.raises(AccessDeniedError):
        await use_case.execute(actor_id=uuid4(), organization_id=uuid4())

    assert reader.arguments is None


@pytest.mark.asyncio
async def test_rejects_unknown_result_filter() -> None:
    use_case = ListAuditEvents(Authorizer(True), Reader([]))

    with pytest.raises(ValueError, match="Unsupported audit result filter"):
        await use_case.execute(actor_id=uuid4(), organization_id=uuid4(), result="unexpected")
