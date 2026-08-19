from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.application.update_platform_ai_moderation_policy import (
    UpdatePlatformAiModerationPolicy,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.ai_moderation_policy import PlatformAiModerationPolicy
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.sessions import SessionAssuranceLevel


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.now_value = now

    def now(self) -> datetime:
        return self.now_value


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(self.allowed)


class Connections:
    def __init__(self, connection: PlatformConnection) -> None:
        self.connection = connection

    async def find_for_organization(self, **_: object) -> PlatformConnection:
        return self.connection


class Policies:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def update_ai_moderation_policy_for_connection(
        self, **arguments: object
    ) -> PlatformAiModerationSummary:
        self.arguments = arguments
        return PlatformAiModerationSummary(
            platform=Platform.DISCORD,
            enforcement_mode="SHADOW",
            test_mode=False,
            is_default_policy=False,
            covered_channel_count=0,
            log_channel_configured=False,
            label_count=0,
            blacklist_word_count=0,
            allowed_domain_count=0,
            automated_timeout_enabled=False,
            automated_kick_enabled=False,
            automated_ban_enabled=False,
        )


class Identifiers:
    def __init__(self) -> None:
        self.value = uuid4()

    def new(self) -> UUID:
        return self.value


class AuditEvents:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event: object) -> None:
        self.events.append(event)


def connection(organization_id: UUID, connection_id: UUID) -> PlatformConnection:
    return PlatformConnection(
        id=connection_id,
        organization_id=organization_id,
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=ConnectionStatus.ACTIVE,
    )


def principal(now: datetime, age: timedelta = timedelta()) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at=now - age,
    )


@pytest.mark.asyncio
async def test_updates_authorized_recent_policy_and_writes_secret_free_audit_event() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    organization_id, connection_id, correlation_id = uuid4(), uuid4(), uuid4()
    policies, audit_events, authorizer = Policies(), AuditEvents(), Authorizer()
    caller = principal(now)
    use_case = UpdatePlatformAiModerationPolicy(
        authorizer=authorizer,
        connections=Connections(connection(organization_id, connection_id)),
        policies=policies,
        recent_authentication=RequireRecentAuthentication(FixedClock(now)),
        identifiers=Identifiers(),
        audit_events=audit_events,
    )

    result = await use_case.execute(
        principal=caller,
        organization_id=organization_id,
        connection_id=connection_id,
        policy=PlatformAiModerationPolicy(Platform.DISCORD),
        correlation_id=correlation_id,
    )

    assert result.enforcement_mode == "SHADOW"
    assert policies.arguments is not None
    assert policies.arguments["actor_id"] == caller.user_id
    assert authorizer.request is not None
    assert authorizer.request.action.value == "manage"
    assert audit_events.events[0].action == "platform_ai_moderation_policy.updated"
    assert audit_events.events[0].result == "succeeded"


@pytest.mark.asyncio
async def test_rejects_stale_session_before_authorization_or_platform_write() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    organization_id, connection_id = uuid4(), uuid4()
    policies, audit_events, authorizer = Policies(), AuditEvents(), Authorizer()
    use_case = UpdatePlatformAiModerationPolicy(
        authorizer=authorizer,
        connections=Connections(connection(organization_id, connection_id)),
        policies=policies,
        recent_authentication=RequireRecentAuthentication(FixedClock(now)),
        identifiers=Identifiers(),
        audit_events=audit_events,
    )

    with pytest.raises(RecentAuthenticationRequiredError):
        await use_case.execute(
            principal=principal(now, timedelta(minutes=16)),
            organization_id=organization_id,
            connection_id=connection_id,
            policy=PlatformAiModerationPolicy(Platform.DISCORD),
            correlation_id=uuid4(),
        )

    assert authorizer.request is None
    assert policies.arguments is None
    assert audit_events.events == []
