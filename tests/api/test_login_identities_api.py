from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.manage_login_identities import (
    LoginIdentityManagementRejectedError,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.identity import LoginIdentityProfile, LoginIdentityProvider
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class SessionResolver:
    def __init__(
        self,
        actor_id: UUID,
        session_id: UUID,
        *,
        assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at: datetime | None = None,
    ) -> None:
        self.actor_id = actor_id
        self.session_id = session_id
        self.assurance_level = assurance_level
        self.authenticated_at = authenticated_at or datetime(2026, 8, 9, tzinfo=UTC)

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id,
            self.session_id,
            self.assurance_level,
            self.authenticated_at,
        )


class IdentityListUseCase:
    def __init__(
        self, identities: tuple[LoginIdentityProfile, ...], rejects: bool = False
    ) -> None:
        self.identities = identities
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise LoginIdentityManagementRejectedError("Access denied.")
        return self.identities


class IdentityUnlinkUseCase:
    def __init__(
        self, identity: LoginIdentityProfile | None = None, rejects: bool = False
    ) -> None:
        self.identity = identity
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if command.principal.assurance_level is not SessionAssuranceLevel.RECENT_AUTHENTICATION:
            raise RecentAuthenticationRequiredError("Recent authentication required.")
        if self.rejects or self.identity is None:
            raise LoginIdentityManagementRejectedError("Unlink denied.")
        return self.identity


def identity(
    user_id: UUID,
    provider: LoginIdentityProvider,
    *,
    identity_id: UUID,
) -> LoginIdentityProfile:
    linked_at = datetime(2026, 8, 9, tzinfo=UTC)
    return LoginIdentityProfile(
        id=identity_id,
        user_id=user_id,
        provider=provider,
        linked_at=linked_at,
        last_used_at=linked_at + timedelta(hours=2),
    )


def authenticated_client(
    *,
    actor_id: UUID,
    session_id: UUID,
    identity_list_use_case=None,
    identity_unlink_use_case=None,
    assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
    authenticated_at: datetime | None = None,
) -> TestClient:
    app = create_app(
        session_resolver=SessionResolver(
            actor_id,
            session_id,
            assurance_level=assurance_level,
            authenticated_at=authenticated_at,
        ),
        login_identity_list_use_case=identity_list_use_case,
        login_identity_unlink_use_case=identity_unlink_use_case,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    return client


def test_lists_login_identities_with_safe_unlink_flags() -> None:
    actor_id = uuid4()
    email_id = uuid4()
    discord_id = uuid4()
    listing = IdentityListUseCase(
        (
            identity(actor_id, LoginIdentityProvider.EMAIL, identity_id=email_id),
            identity(actor_id, LoginIdentityProvider.DISCORD, identity_id=discord_id),
        )
    )
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_list_use_case=listing,
    )

    response = client.get("/api/v1/auth/identities")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(email_id),
                "provider": "email",
                "linked_at": "2026-08-09T00:00:00Z",
                "last_used_at": "2026-08-09T02:00:00Z",
                "can_unlink": False,
            },
            {
                "id": str(discord_id),
                "provider": "discord",
                "linked_at": "2026-08-09T00:00:00Z",
                "last_used_at": "2026-08-09T02:00:00Z",
                "can_unlink": True,
            },
        ]
    }
    assert listing.command.actor_id == actor_id
    assert isinstance(listing.command.correlation_id, UUID)


def test_unlinks_login_identity_with_csrf_and_session_actor() -> None:
    actor_id = uuid4()
    identity_id = uuid4()
    unlinking = IdentityUnlinkUseCase(
        identity(actor_id, LoginIdentityProvider.DISCORD, identity_id=identity_id)
    )
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_unlink_use_case=unlinking,
    )
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.delete(
        f"/api/v1/auth/identities/{identity_id}",
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(identity_id),
        "provider": "discord",
        "linked_at": "2026-08-09T00:00:00Z",
        "last_used_at": "2026-08-09T02:00:00Z",
        "can_unlink": False,
    }
    assert unlinking.command.principal.user_id == actor_id
    assert unlinking.command.principal.session_id is not None
    assert unlinking.command.identity_id == identity_id
    assert isinstance(unlinking.command.correlation_id, UUID)


def test_unlink_login_identity_requires_recent_authentication() -> None:
    actor_id = uuid4()
    identity_id = uuid4()
    unlinking = IdentityUnlinkUseCase(
        identity(actor_id, LoginIdentityProvider.DISCORD, identity_id=identity_id)
    )
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_unlink_use_case=unlinking,
        assurance_level=SessionAssuranceLevel.PASSWORD,
        authenticated_at=datetime(2026, 8, 9, tzinfo=UTC) - timedelta(minutes=20),
    )
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.delete(
        f"/api/v1/auth/identities/{identity_id}",
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Recent authentication is required"}


def test_unlink_login_identity_requires_csrf() -> None:
    actor_id = uuid4()
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_unlink_use_case=IdentityUnlinkUseCase(),
    )

    response = client.delete(f"/api/v1/auth/identities/{uuid4()}")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}


def test_login_identity_listing_hides_rejection_reason() -> None:
    actor_id = uuid4()
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_list_use_case=IdentityListUseCase((), rejects=True),
    )

    response = client.get("/api/v1/auth/identities")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_login_identity_unlink_hides_rejection_reason() -> None:
    actor_id = uuid4()
    client = authenticated_client(
        actor_id=actor_id,
        session_id=uuid4(),
        identity_unlink_use_case=IdentityUnlinkUseCase(rejects=True),
    )
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.delete(
        f"/api/v1/auth/identities/{uuid4()}",
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Login identity unlink failed"}
