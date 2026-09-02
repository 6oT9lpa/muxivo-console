from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.manage_login_identities import (
    ListLoginIdentities,
    ListLoginIdentitiesCommand,
    LoginIdentityManagementRejectedError,
    UnlinkLoginIdentity,
    UnlinkLoginIdentityCommand,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProfile, LoginIdentityProvider, UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel


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


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class IdentityReader:
    def __init__(self, identities: tuple[LoginIdentityProfile, ...]) -> None:
        self.identities = identities
        self.user_id: UUID | None = None

    async def list_for_user(self, *, user_id: UUID) -> tuple[LoginIdentityProfile, ...]:
        self.user_id = user_id
        return self.identities


class IdentityUnlinkWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.identity_id: UUID | None = None
        self.user_id: UUID | None = None
        self.audit_event: AuditEvent | None = None

    async def unlink(self, *, identity_id: UUID, user_id: UUID, audit_event: AuditEvent) -> bool:
        self.identity_id = identity_id
        self.user_id = user_id
        self.audit_event = audit_event
        return self.result


def identity(
    user_id: UUID,
    provider: LoginIdentityProvider,
    *,
    identity_id: UUID | None = None,
) -> LoginIdentityProfile:
    linked_at = datetime(2026, 8, 9, tzinfo=UTC)
    return LoginIdentityProfile(
        id=identity_id or uuid4(),
        user_id=user_id,
        provider=provider,
        linked_at=linked_at,
        last_used_at=linked_at + timedelta(hours=1),
    )


def principal(
    user_id: UUID,
    *,
    now: datetime | None = None,
    level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
    age: timedelta = timedelta(minutes=1),
) -> BrowserSessionPrincipal:
    current_time = now or datetime(2026, 8, 9, tzinfo=UTC)
    return BrowserSessionPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        assurance_level=level,
        authenticated_at=current_time - age,
    )


def recent_auth(now: datetime | None = None) -> RequireRecentAuthentication:
    return RequireRecentAuthentication(FixedClock(now or datetime(2026, 8, 9, tzinfo=UTC)))


@pytest.mark.asyncio
async def test_active_user_lists_login_identities() -> None:
    actor_id = uuid4()
    identities = (
        identity(actor_id, LoginIdentityProvider.EMAIL),
        identity(actor_id, LoginIdentityProvider.DISCORD),
    )
    reader = IdentityReader(identities)
    use_case = ListLoginIdentities(
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=reader,
    )

    listed = await use_case.execute(
        ListLoginIdentitiesCommand(actor_id=actor_id, correlation_id=uuid4())
    )

    assert listed == identities
    assert reader.user_id == actor_id


@pytest.mark.asyncio
async def test_inactive_user_cannot_list_login_identities() -> None:
    use_case = ListLoginIdentities(
        user_statuses=UserStatuses(UserStatus.SUSPENDED),
        identities=IdentityReader(()),
    )

    with pytest.raises(LoginIdentityManagementRejectedError):
        await use_case.execute(ListLoginIdentitiesCommand(actor_id=uuid4(), correlation_id=uuid4()))


@pytest.mark.asyncio
async def test_unlink_non_email_identity_writes_audit_event() -> None:
    actor_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    discord_identity = identity(actor_id, LoginIdentityProvider.DISCORD)
    unlinker = IdentityUnlinkWriter()
    use_case = UnlinkLoginIdentity(
        identifiers=SequenceIdentifiers([audit_id]),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=IdentityReader(
            (
                identity(actor_id, LoginIdentityProvider.EMAIL),
                discord_identity,
            )
        ),
        unlinker=unlinker,
        recent_authentication=recent_auth(),
    )

    unlinked = await use_case.execute(
        UnlinkLoginIdentityCommand(
            principal=principal(actor_id),
            identity_id=discord_identity.id,
            correlation_id=correlation_id,
        )
    )

    assert unlinked == discord_identity
    assert unlinker.identity_id == discord_identity.id
    assert unlinker.user_id == actor_id
    assert unlinker.audit_event is not None
    assert unlinker.audit_event.id == audit_id
    assert unlinker.audit_event.correlation_id == correlation_id
    assert unlinker.audit_event.action == "identity.unlink"
    assert unlinker.audit_event.resource_type == "login_identity"
    assert unlinker.audit_event.resource_id == str(discord_identity.id)


@pytest.mark.asyncio
async def test_unlink_requires_recent_authentication_before_reading_identities() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    actor_id = uuid4()
    reader = IdentityReader(
        (
            identity(actor_id, LoginIdentityProvider.EMAIL),
            identity(actor_id, LoginIdentityProvider.DISCORD),
        )
    )
    unlinker = IdentityUnlinkWriter()
    use_case = UnlinkLoginIdentity(
        identifiers=SequenceIdentifiers([uuid4()]),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=reader,
        unlinker=unlinker,
        recent_authentication=recent_auth(now),
    )

    with pytest.raises(RecentAuthenticationRequiredError):
        await use_case.execute(
            UnlinkLoginIdentityCommand(
                principal=principal(
                    actor_id,
                    now=now,
                    level=SessionAssuranceLevel.PASSWORD,
                    age=timedelta(minutes=20),
                ),
                identity_id=uuid4(),
                correlation_id=uuid4(),
            )
        )

    assert reader.user_id is None
    assert unlinker.audit_event is None


@pytest.mark.asyncio
async def test_email_identity_cannot_be_unlinked() -> None:
    actor_id = uuid4()
    email_identity = identity(actor_id, LoginIdentityProvider.EMAIL)
    use_case = UnlinkLoginIdentity(
        identifiers=SequenceIdentifiers([uuid4()]),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=IdentityReader(
            (
                email_identity,
                identity(actor_id, LoginIdentityProvider.DISCORD),
            )
        ),
        unlinker=IdentityUnlinkWriter(),
        recent_authentication=recent_auth(),
    )

    with pytest.raises(LoginIdentityManagementRejectedError):
        await use_case.execute(
            UnlinkLoginIdentityCommand(
                principal=principal(actor_id),
                identity_id=email_identity.id,
                correlation_id=uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_last_usable_identity_cannot_be_unlinked() -> None:
    actor_id = uuid4()
    discord_identity = identity(actor_id, LoginIdentityProvider.DISCORD)
    use_case = UnlinkLoginIdentity(
        identifiers=SequenceIdentifiers([uuid4()]),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=IdentityReader((discord_identity,)),
        unlinker=IdentityUnlinkWriter(),
        recent_authentication=recent_auth(),
    )

    with pytest.raises(LoginIdentityManagementRejectedError):
        await use_case.execute(
            UnlinkLoginIdentityCommand(
                principal=principal(actor_id),
                identity_id=discord_identity.id,
                correlation_id=uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_unlink_conflict_fails_closed() -> None:
    actor_id = uuid4()
    discord_identity = identity(actor_id, LoginIdentityProvider.DISCORD)
    use_case = UnlinkLoginIdentity(
        identifiers=SequenceIdentifiers([uuid4()]),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        identities=IdentityReader(
            (
                identity(actor_id, LoginIdentityProvider.EMAIL),
                discord_identity,
            )
        ),
        unlinker=IdentityUnlinkWriter(result=False),
        recent_authentication=recent_auth(),
    )

    with pytest.raises(LoginIdentityManagementRejectedError):
        await use_case.execute(
            UnlinkLoginIdentityCommand(
                principal=principal(actor_id),
                identity_id=discord_identity.id,
                correlation_id=uuid4(),
            )
        )
