from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.link_verified_identity import (
    IdentityLinkRejectedError,
    LinkVerifiedIdentity,
    LinkVerifiedIdentityCommand,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentity, LoginIdentityProvider, UserStatus


class Identifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class UserStatuses:
    def __init__(self, status: UserStatus | None) -> None:
        self.status = status

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


class IdentityWriter:
    def __init__(self, linked: bool = True) -> None:
        self.linked = linked
        self.identity: LoginIdentity | None = None
        self.audit_event: AuditEvent | None = None

    async def link(self, *, identity: LoginIdentity, audit_event: AuditEvent) -> bool:
        self.identity = identity
        self.audit_event = audit_event
        return self.linked


def command(
    provider: LoginIdentityProvider = LoginIdentityProvider.DISCORD,
) -> LinkVerifiedIdentityCommand:
    return LinkVerifiedIdentityCommand(uuid4(), provider, "123456789012345678", uuid4())


@pytest.mark.asyncio
async def test_links_only_verified_non_email_identity_for_active_user_with_audit() -> None:
    requested = command()
    identity_id, audit_id = uuid4(), uuid4()
    writer = IdentityWriter()
    use_case = LinkVerifiedIdentity(
        Identifiers([identity_id, audit_id]), UserStatuses(UserStatus.ACTIVE), writer
    )

    identity = await use_case.execute(requested)

    assert identity.id == identity_id
    assert identity.user_id == requested.actor_id
    assert identity.provider is LoginIdentityProvider.DISCORD
    assert identity.provider_subject == "123456789012345678"
    assert writer.audit_event.action == "identity.link"
    assert writer.audit_event.resource_id == str(identity_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", (None, UserStatus.PENDING_VERIFICATION, UserStatus.SUSPENDED))
async def test_inactive_user_cannot_link_provider_identity(status: UserStatus | None) -> None:
    writer = IdentityWriter()
    use_case = LinkVerifiedIdentity(Identifiers([uuid4(), uuid4()]), UserStatuses(status), writer)

    with pytest.raises(IdentityLinkRejectedError):
        await use_case.execute(command())

    assert writer.identity is None


@pytest.mark.asyncio
async def test_does_not_allow_browser_or_adapter_to_link_email_as_external_identity() -> None:
    writer = IdentityWriter()
    use_case = LinkVerifiedIdentity(
        Identifiers([uuid4(), uuid4()]), UserStatuses(UserStatus.ACTIVE), writer
    )

    with pytest.raises(IdentityLinkRejectedError):
        await use_case.execute(command(LoginIdentityProvider.EMAIL))

    assert writer.identity is None


@pytest.mark.asyncio
async def test_duplicate_provider_subject_is_a_safe_failure() -> None:
    use_case = LinkVerifiedIdentity(
        Identifiers([uuid4(), uuid4()]), UserStatuses(UserStatus.ACTIVE), IdentityWriter(False)
    )

    with pytest.raises(IdentityLinkRejectedError):
        await use_case.execute(command())
