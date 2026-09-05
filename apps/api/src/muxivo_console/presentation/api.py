import logging
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hmac import compare_digest
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response

from muxivo_console.application.accept_organization_invitation import (
    AcceptOrganizationInvitation,
    AcceptOrganizationInvitationCommand,
    OrganizationInvitationAcceptanceRejectedError,
)
from muxivo_console.application.authenticate_email_password import (
    AuthenticateEmailPassword,
    AuthenticateEmailPasswordCommand,
    AuthenticationRejectedError,
)
from muxivo_console.application.begin_identity_link import (
    BeginIdentityLink,
    BeginIdentityLinkCommand,
    IdentityLinkStartRejectedError,
)
from muxivo_console.application.begin_oauth_login import (
    BeginOAuthLogin,
    OAuthLoginStartRejectedError,
)
from muxivo_console.application.change_email_password import (
    ChangeEmailPassword,
    ChangeEmailPasswordCommand,
    PasswordChangeRejectedError,
)
from muxivo_console.application.complete_identity_link import (
    CompleteIdentityLink,
    CompleteIdentityLinkCommand,
    IdentityLinkCompletionRejectedError,
)
from muxivo_console.application.complete_oauth_login import (
    CompleteOAuthLogin,
    OAuthLoginCompletionRejectedError,
)
from muxivo_console.application.complete_password_recovery import (
    CompletePasswordRecovery,
    CompletePasswordRecoveryCommand,
    PasswordRecoveryCompletionRejectedError,
)
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.application.create_organization import (
    CreateOrganization,
    CreateOrganizationCommand,
    OrganizationCreationRejectedError,
)
from muxivo_console.application.email_password_registration_verification_rejected_error import (
    EmailPasswordRegistrationVerificationRejectedError,
)
from muxivo_console.application.get_platform_ai_moderation_policy import (
    GetPlatformAiModerationPolicy,
)
from muxivo_console.application.get_platform_ai_moderation_summary import (
    GetPlatformAiModerationSummary,
)
from muxivo_console.application.get_platform_audit_timeline import GetPlatformAuditTimeline
from muxivo_console.application.get_platform_bot_settings import GetPlatformBotSettings
from muxivo_console.application.get_platform_channel_purposes import (
    GetPlatformChannelPurposes,
)
from muxivo_console.application.get_platform_dashboard_summary import (
    GetPlatformDashboardSummary,
)
from muxivo_console.application.get_platform_health import (
    GetPlatformHealth,
    PlatformHealthUnavailableError,
)
from muxivo_console.application.get_platform_integrations import GetPlatformIntegrations
from muxivo_console.application.get_platform_server_statistics import (
    GetPlatformServerStatistics,
)
from muxivo_console.application.get_platform_welcome_settings import (
    GetPlatformWelcomeSettings,
)
from muxivo_console.application.invite_organization_member import (
    InviteOrganizationMember,
    InviteOrganizationMemberCommand,
    OrganizationInvitationRejectedError,
)
from muxivo_console.application.list_browser_sessions import (
    BrowserSessionListRejectedError,
    BrowserSessionSecurityView,
    ListBrowserSessions,
    ListBrowserSessionsCommand,
)
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    ListControlModules,
    PlatformControlUnavailableError,
)
from muxivo_console.application.list_organization_audit_events import (
    ListOrganizationAuditEvents,
)
from muxivo_console.application.list_organization_invitations import (
    ListOrganizationInvitations,
    ListOrganizationInvitationsCommand,
    OrganizationInvitationListingRejectedError,
)
from muxivo_console.application.list_organizations import (
    ListOrganizations,
    ListOrganizationsCommand,
    OrganizationListRejectedError,
)
from muxivo_console.application.list_platform_connection_candidates import (
    ListPlatformConnectionCandidates,
    ListPlatformConnectionCandidatesCommand,
)
from muxivo_console.application.list_platform_connection_channels import (
    ListPlatformConnectionChannels,
)
from muxivo_console.application.list_platform_connections import ListPlatformConnections
from muxivo_console.application.manage_login_identities import (
    ListLoginIdentities,
    ListLoginIdentitiesCommand,
    LoginIdentityManagementRejectedError,
    UnlinkLoginIdentity,
    UnlinkLoginIdentityCommand,
)
from muxivo_console.application.manage_organization_members import (
    AddOrganizationMember,
    AddOrganizationMemberCommand,
    ListOrganizationMembers,
    ListOrganizationMembersCommand,
    OrganizationMemberManagementRejectedError,
    RemoveOrganizationMember,
    RemoveOrganizationMemberCommand,
    UpdateOrganizationMember,
    UpdateOrganizationMemberCommand,
)
from muxivo_console.application.manage_platform_connection_lifecycle import (
    ManagePlatformConnectionLifecycle,
    ManagePlatformConnectionLifecycleCommand,
    PlatformConnectionLifecycleAction,
    PlatformConnectionLifecycleRejectedError,
)
from muxivo_console.application.ports import (
    HttpMetricsRecorder,
    RateLimiter,
    ReadinessProbe,
    SessionFingerprintHasher,
)
from muxivo_console.application.reauthenticate_browser_session import (
    BrowserSessionReauthenticationRejectedError,
    ReauthenticateBrowserSession,
    ReauthenticateBrowserSessionCommand,
)
from muxivo_console.application.connect_platform_connection import (
    PlatformConnectionConnectRejectedError,
    ConnectPlatformConnection,
    ConnectPlatformConnectionCommand,
)
from muxivo_console.application.request_password_recovery import (
    RequestPasswordRecovery,
    RequestPasswordRecoveryCommand,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
)
from muxivo_console.application.resend_email_password_registration_command import (
    ResendEmailPasswordRegistrationCommand,
)
from muxivo_console.application.resolve_browser_session import (
    BrowserSessionPrincipal,
    ResolveBrowserSession,
)
from muxivo_console.application.revoke_all_browser_sessions import (
    BrowserSessionBulkRevocationRejectedError,
    RevokeAllBrowserSessions,
    RevokeAllBrowserSessionsCommand,
)
from muxivo_console.application.revoke_browser_session import RevokeBrowserSession
from muxivo_console.application.revoke_organization_invitation import (
    OrganizationInvitationRevocationRejectedError,
    RevokeOrganizationInvitation,
    RevokeOrganizationInvitationCommand,
)
from muxivo_console.application.start_email_password_registration import (
    StartEmailPasswordRegistration,
)
from muxivo_console.application.start_email_password_registration_command import (
    StartEmailPasswordRegistrationCommand,
)
from muxivo_console.application.update_platform_ai_moderation_policy import (
    UpdatePlatformAiModerationPolicy,
)
from muxivo_console.application.update_platform_channel_purpose import (
    UpdatePlatformChannelPurpose,
)
from muxivo_console.application.update_platform_welcome_settings import (
    UpdatePlatformWelcomeSettings,
)
from muxivo_console.application.verify_email_password_registration import (
    VerifyEmailPasswordRegistration,
)
from muxivo_console.application.verify_email_password_registration_command import (
    VerifyEmailPasswordRegistrationCommand,
)
from muxivo_console.contracts.v1.ai_moderation_policy import (
    AiModerationPolicyUpdateRequest,
    PlatformAiModerationPolicyResponse,
)
from muxivo_console.contracts.v1.audit_events import AuditEventListResponse, AuditEventResponse
from muxivo_console.contracts.v1.authentication import (
    BrowserSessionReauthenticationRequest,
    EmailPasswordLoginRequest,
    EmailPasswordRegistrationRequest,
    EmailPasswordRegistrationResponse,
    EmailPasswordRegistrationVerificationRequest,
    EmailPasswordRegistrationVerificationResendRequest,
    EmailPasswordRegistrationVerificationResponse,
    OAuthProviderCatalogResponse,
    PasswordChangeRequest,
    PasswordRecoveryCompletionRequest,
    PasswordRecoveryRequest,
    PasswordRecoveryRequestResponse,
)
from muxivo_console.contracts.v1.control_modules import (
    ControlModuleListResponse,
    ControlModuleResponse,
)
from muxivo_console.contracts.v1.identities import (
    LoginIdentityListResponse,
    LoginIdentityResponse,
)
from muxivo_console.contracts.v1.organizations import (
    OrganizationCreateRequest,
    OrganizationInvitationAcceptRequest,
    OrganizationInvitationCreateRequest,
    OrganizationInvitationListResponse,
    OrganizationInvitationResponse,
    OrganizationListItemResponse,
    OrganizationListResponse,
    OrganizationMemberCreateRequest,
    OrganizationMemberListResponse,
    OrganizationMembershipResponse,
    OrganizationMembershipScopeRequest,
    OrganizationMembershipScopeResponse,
    OrganizationMemberUpdateRequest,
    OrganizationResponse,
)
from muxivo_console.contracts.v1.platform_ai_moderation import (
    PlatformAiModerationSummaryResponse,
)
from muxivo_console.contracts.v1.platform_audit_timeline import (
    PlatformAuditTimelineResponse,
)
from muxivo_console.contracts.v1.platform_bot_settings import PlatformBotSettingsResponse
from muxivo_console.contracts.v1.platform_channel_purposes import (
    ChannelPurposeAssignmentResponse,
    ChannelPurposeUpdateRequest,
    PlatformChannelPurposesResponse,
)
from muxivo_console.contracts.v1.platform_channels import (
    PlatformChannelCatalogResponse,
    PlatformChannelResponse,
)
from muxivo_console.contracts.v1.platform_connections import (
    PlatformConnectionCandidateListResponse,
    PlatformConnectionCandidateResponse,
    PlatformConnectionCreateRequest,
    PlatformConnectionGrantedScopeResponse,
    PlatformConnectionListResponse,
    PlatformConnectionResponse,
)
from muxivo_console.contracts.v1.platform_dashboard import PlatformDashboardSummaryResponse
from muxivo_console.contracts.v1.platform_health import (
    HealthSignalResponse,
    PlatformHealthResponse,
)
from muxivo_console.contracts.v1.platform_integrations import PlatformIntegrationsResponse
from muxivo_console.contracts.v1.platform_server_statistics import (
    PlatformServerStatisticsResponse,
)
from muxivo_console.contracts.v1.platform_welcome import (
    PlatformWelcomeSettingsResponse,
    PlatformWelcomeSettingsUpdateRequest,
)
from muxivo_console.contracts.v1.sessions import (
    BrowserSessionBulkRevocationResponse,
    BrowserSessionListResponse,
    BrowserSessionResponse,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.identity import LoginIdentityProfile, LoginIdentityProvider
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
)
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    OrganizationMemberProfile,
    OrganizationMembership,
)
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.domain.welcome import PlatformWelcomeSettings
from muxivo_console.infrastructure.development import (
    DenyByDefaultOrganizationAuthorizer,
    StaticModuleCatalog,
)
from muxivo_console.presentation.background_service import BackgroundService
from muxivo_console.presentation.browser_security_constants import (
    CSRF_COOKIE_NAME,
    DEFAULT_CONTENT_SECURITY_POLICY,
    SESSION_COOKIE_NAME,
)
from muxivo_console.presentation.browser_security_policy import BrowserSecurityPolicy
from muxivo_console.presentation.browser_session_cookie_settings import (
    BrowserSessionCookieSettings,
)

__all__ = [
    "BrowserSecurityPolicy",
    "BrowserSessionCookieSettings",
    "CSRF_COOKIE_NAME",
    "DEFAULT_CONTENT_SECURITY_POLICY",
    "SESSION_COOKIE_NAME",
    "create_app",
]

CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/email-password/registrations",
        "/api/v1/auth/email-password/registration-verifications",
        "/api/v1/auth/email-password/registration-verifications/resend",
        "/api/v1/auth/email-password/sessions",
        "/api/v1/auth/discord/authorizations",
        "/api/v1/auth/twitch/authorizations",
        "/api/v1/auth/telegram/authorizations",
        "/api/v1/auth/google/authorizations",
        "/api/v1/auth/yandex/authorizations",
        "/api/v1/auth/password-recovery/requests",
        "/api/v1/auth/password-recovery/completions",
    }
)
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
logger = logging.getLogger(__name__)


def _set_browser_session_cookies(
    response: Response,
    session: IssuedBrowserSession,
    cookies: BrowserSessionCookieSettings,
) -> None:
    response.set_cookie(
        key=cookies.session_name,
        value=session.raw_token,
        expires=session.expires_at,
        path="/",
        secure=cookies.secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=cookies.csrf_name,
        value=session.raw_csrf_token,
        expires=session.expires_at,
        path="/",
        secure=cookies.secure,
        httponly=False,
        samesite="lax",
    )


def _membership_response(
    membership: OrganizationMembership,
    *,
    display_name: str | None = None,
) -> OrganizationMembershipResponse:
    return OrganizationMembershipResponse(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=membership.actor_id,
        display_name=display_name,
        role=membership.role,
        resource_scopes=[
            OrganizationMembershipScopeResponse(
                id=scope.id,
                resource=scope.resource,
                action=scope.action,
            )
            for scope in sorted(
                membership.resource_scopes,
                key=lambda item: (item.resource.value, item.action.value, str(item.id)),
            )
        ],
    )


def _organization_invitation_response(
    invitation: OrganizationInvitation,
    *,
    now: datetime,
    delivery_status: str | None = None,
) -> OrganizationInvitationResponse:
    resolved_delivery_status = delivery_status
    if resolved_delivery_status is None and invitation.delivery_status is not None:
        resolved_delivery_status = invitation.delivery_status.value
    return OrganizationInvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email_hint=invitation.email_hint,
        role=invitation.role,
        resource_scopes=[
            OrganizationMembershipScopeResponse(
                id=scope.id,
                resource=scope.resource,
                action=scope.action,
            )
            for scope in sorted(
                invitation.resource_scopes,
                key=lambda item: (item.resource.value, item.action.value, str(item.id)),
            )
        ],
        status=invitation.status_at(now),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        delivery_status=resolved_delivery_status,
    )


def _organization_member_response(
    member: OrganizationMemberProfile | OrganizationMembership,
) -> OrganizationMembershipResponse:
    if isinstance(member, OrganizationMemberProfile):
        return _membership_response(member.membership, display_name=member.display_name)
    return _membership_response(member)


def _scope_requests_to_domain(
    scopes: list[OrganizationMembershipScopeRequest],
) -> tuple[MembershipResourceScope, ...]:
    return tuple(
        MembershipResourceScope(resource=scope.resource, action=scope.action) for scope in scopes
    )


def _platform_connection_candidate_response(
    catalog: PlatformConnectionCandidateCatalog,
) -> PlatformConnectionCandidateListResponse:
    return PlatformConnectionCandidateListResponse(
        platform=catalog.platform,
        identity_linked=catalog.identity_linked,
        items=[
            PlatformConnectionCandidateResponse(
                platform=candidate.platform,
                external_resource_id=candidate.external_resource_id,
                display_name=candidate.display_name,
            )
            for candidate in catalog.items
        ],
    )


def _platform_connection_response(connection: PlatformConnection) -> PlatformConnectionResponse:
    return PlatformConnectionResponse(
        id=connection.id,
        organization_id=connection.organization_id,
        platform=connection.platform,
        external_resource_id=connection.external_resource_id,
        status=connection.status,
        status_reason=connection.status_reason,
        granted_scopes=[
            PlatformConnectionGrantedScopeResponse(
                key=key,
                display_name=display_name,
                description=description,
                status=_scope_status_for_connection(connection.status),
            )
            for key, display_name, description in _scope_catalog_for_platform(connection.platform)
        ],
    )


def _scope_status_for_connection(
    status: ConnectionStatus,
) -> str:
    if status is ConnectionStatus.PENDING:
        return "pending"
    if status in {ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}:
        return "granted"
    if status is ConnectionStatus.REAUTH_REQUIRED:
        return "requires_reauthorization"
    return "revoked"


def _scope_catalog_for_platform(platform: Platform) -> tuple[tuple[str, str, str], ...]:
    if platform is Platform.DISCORD:
        return (
            (
                "discord.guild.read",
                "Read Discord server metadata",
                "Lets Console show safe aggregate server, channel and health information.",
            ),
            (
                "discord.guild.manage",
                "Manage Discord server settings",
                "Lets Console request server-side Control API changes after native admin checks.",
            ),
        )
    if platform is Platform.TWITCH:
        return (
            (
                "twitch.channel.read",
                "Read Twitch channel metadata",
                "Lets Console show safe aggregate channel and connection health information.",
            ),
            (
                "twitch.channel.manage",
                "Manage Twitch channel controls",
                "Lets Console request server-side Control API changes after native owner checks.",
            ),
        )
    return (
        (
            "telegram.chat.read",
            "Read Telegram chat metadata",
            "Lets Console show safe aggregate chat and connection health information.",
        ),
        (
            "telegram.chat.manage",
            "Manage Telegram chat controls",
            "Lets Console request server-side Control API changes after native owner checks.",
        ),
    )


def _browser_session_response(view: BrowserSessionSecurityView) -> BrowserSessionResponse:
    session = view.session
    return BrowserSessionResponse(
        id=session.id,
        is_current=view.is_current,
        assurance_level=session.assurance_level,
        authenticated_at=session.authenticated_at,
        last_seen_at=session.last_seen_at or session.authenticated_at,
        expires_at=session.expires_at,
        device_label=_fingerprint_label("Browser", session.user_agent_hash),
        ip_fingerprint=_fingerprint_label("ip", session.ip_hash),
        user_agent_fingerprint=_fingerprint_label("ua", session.user_agent_hash),
    )


def _fingerprint_label(prefix: str, value: str | None) -> str | None:
    if value is None:
        return None if prefix != "Browser" else "Unknown browser"
    return f"{prefix}:{value[:12]}"


def _request_client_ip(request: Request) -> str | None:
    """Read the trusted ASGI client address without putting it in application logs."""
    if request.client is None or not request.client.host:
        return None
    return request.client.host


def _client_log_fingerprint(hasher: SessionFingerprintHasher | None, client_host: str) -> str:
    """Keep rate-limit telemetry useful without exposing a raw client address."""
    if hasher is None:
        return "unavailable"
    return f"ip:{hasher.hash_ip_address(client_host)[:12]}"


def _login_identity_response(
    identity: LoginIdentityProfile, *, total_identity_count: int
) -> LoginIdentityResponse:
    return LoginIdentityResponse(
        id=identity.id,
        provider=identity.provider,
        linked_at=identity.linked_at,
        last_used_at=identity.last_used_at,
        can_unlink=(
            identity.provider is not LoginIdentityProvider.EMAIL and total_identity_count > 1
        ),
    )


def create_app(
    control_modules_use_case: ListControlModules | None = None,
    registration_verification_start_use_case: StartEmailPasswordRegistration | None = None,
    registration_verification_use_case: VerifyEmailPasswordRegistration | None = None,
    authentication_use_case: AuthenticateEmailPassword | None = None,
    password_change_use_case: ChangeEmailPassword | None = None,
    password_recovery_request_use_case: RequestPasswordRecovery | None = None,
    password_recovery_completion_use_case: CompletePasswordRecovery | None = None,
    rate_limiter: RateLimiter | None = None,
    metrics_recorder: HttpMetricsRecorder | None = None,
    readiness_probe: ReadinessProbe | None = None,
    organization_creation_use_case: CreateOrganization | None = None,
    organization_list_use_case: ListOrganizations | None = None,
    organization_members_use_case: ListOrganizationMembers | None = None,
    organization_member_add_use_case: AddOrganizationMember | None = None,
    organization_member_update_use_case: UpdateOrganizationMember | None = None,
    organization_member_remove_use_case: RemoveOrganizationMember | None = None,
    organization_invitation_create_use_case: InviteOrganizationMember | None = None,
    organization_invitation_list_use_case: ListOrganizationInvitations | None = None,
    organization_invitation_revoke_use_case: RevokeOrganizationInvitation | None = None,
    organization_invitation_accept_use_case: AcceptOrganizationInvitation | None = None,
    platform_connection_connect_use_case: ConnectPlatformConnection | None = None,
    platform_connection_candidates_use_case: ListPlatformConnectionCandidates | None = None,
    platform_connection_lifecycle_use_case: ManagePlatformConnectionLifecycle | None = None,
    platform_connections_use_case: ListPlatformConnections | None = None,
    audit_events_use_case: ListOrganizationAuditEvents | None = None,
    platform_health_use_case: GetPlatformHealth | None = None,
    platform_audit_timeline_use_case: GetPlatformAuditTimeline | None = None,
    platform_dashboard_use_case: GetPlatformDashboardSummary | None = None,
    platform_channels_use_case: ListPlatformConnectionChannels | None = None,
    platform_channel_purposes_use_case: GetPlatformChannelPurposes | None = None,
    platform_ai_moderation_summary_use_case: GetPlatformAiModerationSummary | None = None,
    platform_bot_settings_use_case: GetPlatformBotSettings | None = None,
    platform_integrations_use_case: GetPlatformIntegrations | None = None,
    platform_server_statistics_use_case: GetPlatformServerStatistics | None = None,
    platform_ai_moderation_policy_use_case: GetPlatformAiModerationPolicy | None = None,
    platform_ai_moderation_policy_update_use_case: UpdatePlatformAiModerationPolicy | None = None,
    platform_channel_purpose_update_use_case: UpdatePlatformChannelPurpose | None = None,
    platform_welcome_settings_use_case: GetPlatformWelcomeSettings | None = None,
    platform_welcome_settings_update_use_case: UpdatePlatformWelcomeSettings | None = None,
    discord_identity_link_start: BeginIdentityLink | None = None,
    discord_identity_link_complete: CompleteIdentityLink | None = None,
    twitch_identity_link_start: BeginIdentityLink | None = None,
    twitch_identity_link_complete: CompleteIdentityLink | None = None,
    discord_login_start: BeginOAuthLogin | None = None,
    discord_login_complete: CompleteOAuthLogin | None = None,
    twitch_login_start: BeginOAuthLogin | None = None,
    twitch_login_complete: CompleteOAuthLogin | None = None,
    google_identity_link_start: BeginIdentityLink | None = None,
    google_identity_link_complete: CompleteIdentityLink | None = None,
    google_login_start: BeginOAuthLogin | None = None,
    google_login_complete: CompleteOAuthLogin | None = None,
    yandex_identity_link_start: BeginIdentityLink | None = None,
    yandex_identity_link_complete: CompleteIdentityLink | None = None,
    yandex_login_start: BeginOAuthLogin | None = None,
    yandex_login_complete: CompleteOAuthLogin | None = None,
    telegram_identity_link_start: BeginIdentityLink | None = None,
    telegram_identity_link_complete: CompleteIdentityLink | None = None,
    telegram_login_start: BeginOAuthLogin | None = None,
    telegram_login_complete: CompleteOAuthLogin | None = None,
    discord_authorization_url: Callable[..., str] | None = None,
    twitch_authorization_url: Callable[..., str] | None = None,
    google_authorization_url: Callable[..., str] | None = None,
    yandex_authorization_url: Callable[..., str] | None = None,
    telegram_authorization_url: Callable[..., str] | None = None,
    session_resolver: ResolveBrowserSession | None = None,
    session_revoker: RevokeBrowserSession | None = None,
    session_list_use_case: ListBrowserSessions | None = None,
    session_bulk_revoker: RevokeAllBrowserSessions | None = None,
    session_reauthentication_use_case: ReauthenticateBrowserSession | None = None,
    login_identity_list_use_case: ListLoginIdentities | None = None,
    login_identity_unlink_use_case: UnlinkLoginIdentity | None = None,
    browser_session_cookies: BrowserSessionCookieSettings | None = None,
    browser_security_policy: BrowserSecurityPolicy | None = None,
    session_fingerprint_hasher: SessionFingerprintHasher | None = None,
    background_services: Sequence[BackgroundService] = (),
) -> FastAPI:
    """Create the Console BFF without coupling application code to FastAPI."""
    cookies = browser_session_cookies or BrowserSessionCookieSettings()
    security_policy = browser_security_policy or BrowserSecurityPolicy()
    control_modules = control_modules_use_case or ListControlModules(
        authorizer=DenyByDefaultOrganizationAuthorizer(),
        catalog=StaticModuleCatalog(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        started_services: list[BackgroundService] = []
        logger.info(
            "application.starting",
            extra={"background_service_count": len(background_services)},
        )
        try:
            for service in background_services:
                logger.info(
                    "background_service.starting",
                    extra={"service_type": type(service).__name__},
                )
                await service.start()
                started_services.append(service)
                logger.info(
                    "background_service.started",
                    extra={"service_type": type(service).__name__},
                )
            logger.info("application.started")
            yield
        finally:
            for service in reversed(started_services):
                logger.info(
                    "background_service.stopping",
                    extra={"service_type": type(service).__name__},
                )
                await service.stop()
                logger.info(
                    "background_service.stopped",
                    extra={"service_type": type(service).__name__},
                )
            logger.info("application.stopped")

    app = FastAPI(title="Muxivo Console API", version="1.0.0", lifespan=lifespan)
    if security_policy.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(security_policy.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[CSRF_HEADER_NAME, "Content-Type", "Idempotency-Key"],
        )

    def apply_browser_security_headers(response: Response) -> Response:
        response.headers.setdefault(
            "Content-Security-Policy",
            security_policy.content_security_policy,
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if security_policy.hsts_enabled:
            response.headers.setdefault("Strict-Transport-Security", security_policy.hsts_value)
        return response

    @app.middleware("http")
    async def attach_browser_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        return apply_browser_security_headers(response)

    @app.middleware("http")
    async def attach_correlation_id(request: Request, call_next) -> Response:
        correlation_id = uuid4()
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        except Exception as error:
            logger.error(
                "http.unhandled_error",
                extra={
                    "correlation_id": str(correlation_id),
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(error).__name__,
                },
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
            response = apply_browser_security_headers(response)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        return response

    @app.middleware("http")
    async def resolve_browser_session(request: Request, call_next) -> Response:
        if session_resolver is not None:
            raw_token = request.cookies.get(cookies.session_name)
            if raw_token is not None:
                try:
                    principal = await session_resolver.execute(raw_token)
                except Exception as error:
                    logger.warning(
                        "auth.session.resolve_failed",
                        extra={
                            "correlation_id": str(request.state.correlation_id),
                            "error_type": type(error).__name__,
                        },
                    )
                    principal = None
                if principal is not None:
                    request.state.actor_id = principal.user_id
                    request.state.session_id = principal.session_id
                    request.state.assurance_level = principal.assurance_level
                    request.state.authenticated_at = principal.authenticated_at
        return await call_next(request)

    @app.middleware("http")
    async def protect_mutations_from_csrf(request: Request, call_next) -> Response:
        """Require a browser-readable token to accompany every authenticated mutation."""
        if request.method not in SAFE_HTTP_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            csrf_cookie = request.cookies.get(cookies.csrf_name)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_cookie or not csrf_header or not compare_digest(csrf_cookie, csrf_header):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF validation failed"},
                )
        return await call_next(request)

    @app.middleware("http")
    async def record_http_metrics(request: Request, call_next) -> Response:
        started_at = perf_counter()
        correlation_id = str(getattr(request.state, "correlation_id", "")) or None
        logger.info(
            "http.request.started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "correlation_id": correlation_id,
            },
        )
        try:
            response = await call_next(request)
        except Exception as error:
            logger.error(
                "http.request.failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(error).__name__,
                    "duration_seconds": perf_counter() - started_at,
                    "correlation_id": str(getattr(request.state, "correlation_id", "")) or None,
                },
            )
            raise
        duration_seconds = perf_counter() - started_at
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        if metrics_recorder is not None:
            metrics_recorder.record_http_request(
                method=request.method,
                route=route_path,
                status_code=response.status_code,
                duration_seconds=duration_seconds,
            )
        logger.info(
            "http.request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "route": route_path,
                "status_code": response.status_code,
                "duration_seconds": round(duration_seconds, 6),
                "correlation_id": str(getattr(request.state, "correlation_id", "")) or None,
            },
        )
        return response

    async def enforce_auth_rate_limit(request: Request, *, scope: str) -> None:
        if rate_limiter is None:
            return
        client_host = request.client.host if request.client is not None else "unknown"
        decision = await rate_limiter.check(scope=scope, key=client_host)
        client_fingerprint = _client_log_fingerprint(session_fingerprint_hasher, client_host)
        if decision.allowed:
            logger.info(
                "auth.rate_limit.allowed",
                extra={
                    "scope": scope,
                    "client_fingerprint": client_fingerprint,
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            return
        logger.warning(
            "auth.rate_limit.denied",
            extra={
                "scope": scope,
                "client_fingerprint": client_fingerprint,
                "retry_after_seconds": decision.retry_after_seconds,
                "correlation_id": str(request.state.correlation_id),
            },
        )
        headers = {"Retry-After": str(max(1, decision.retry_after_seconds))}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers=headers,
        )

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["operations"])
    async def readyz(request: Request) -> dict[str, str]:
        if readiness_probe is None:
            logger.error(
                "operations.readiness.unavailable",
                extra={"correlation_id": str(request.state.correlation_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Readiness is unavailable",
            )
        try:
            ready = await readiness_probe.check(
                correlation_id=request.state.correlation_id,
            )
        except Exception as error:
            logger.error(
                "operations.readiness.check_failed",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            ready = False
        if not ready:
            logger.warning(
                "operations.readiness.failed",
                extra={"correlation_id": str(request.state.correlation_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is not ready",
            )
        logger.info(
            "operations.readiness.completed",
            extra={"correlation_id": str(request.state.correlation_id)},
        )
        return {"status": "ok"}

    @app.get("/metrics", tags=["operations"])
    async def metrics(request: Request) -> Response:
        if metrics_recorder is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Metrics are unavailable",
            )
        logger.info(
            "operations.metrics.rendered",
            extra={"correlation_id": str(request.state.correlation_id)},
        )
        return Response(
            content=metrics_recorder.render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/api/v1/auth/session", tags=["authentication"])
    async def get_browser_session(request: Request) -> dict[str, bool]:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return {"authenticated": True}

    @app.delete(
        "/api/v1/auth/session", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"]
    )
    async def revoke_browser_session(request: Request) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        if not isinstance(actor_id, UUID) or not isinstance(session_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if session_revoker is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session revocation is unavailable",
            )
        try:
            await session_revoker.execute(
                user_id=actor_id, session_id=session_id, correlation_id=request.state.correlation_id
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            key=cookies.session_name,
            path="/",
            secure=cookies.secure,
            httponly=True,
            samesite="lax",
        )
        response.delete_cookie(
            key=cookies.csrf_name,
            path="/",
            secure=cookies.secure,
            httponly=False,
            samesite="lax",
        )
        return response

    @app.get(
        "/api/v1/auth/sessions",
        response_model=BrowserSessionListResponse,
        tags=["authentication"],
    )
    async def list_browser_sessions(request: Request) -> BrowserSessionListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        if not isinstance(actor_id, UUID) or not isinstance(session_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if session_list_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session listing is unavailable",
            )
        try:
            sessions = await session_list_use_case.execute(
                ListBrowserSessionsCommand(
                    actor_id=actor_id,
                    current_session_id=session_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except BrowserSessionListRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return BrowserSessionListResponse(
            items=[_browser_session_response(session) for session in sessions]
        )

    @app.delete(
        "/api/v1/auth/sessions",
        response_model=BrowserSessionBulkRevocationResponse,
        tags=["authentication"],
    )
    async def revoke_all_browser_sessions(request: Request) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        assurance_level = getattr(request.state, "assurance_level", None)
        authenticated_at = getattr(request.state, "authenticated_at", None)
        if (
            not isinstance(actor_id, UUID)
            or not isinstance(session_id, UUID)
            or not isinstance(assurance_level, SessionAssuranceLevel)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if session_bulk_revoker is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session bulk revocation is unavailable",
            )
        try:
            revoked_count = await session_bulk_revoker.execute(
                RevokeAllBrowserSessionsCommand(
                    principal=BrowserSessionPrincipal(
                        user_id=actor_id,
                        session_id=session_id,
                        assurance_level=assurance_level,
                        authenticated_at=authenticated_at,
                    ),
                    correlation_id=request.state.correlation_id,
                )
            )
        except RecentAuthenticationRequiredError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent authentication required",
            ) from error
        except BrowserSessionBulkRevocationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=BrowserSessionBulkRevocationResponse(revoked_count=revoked_count).model_dump(),
        )
        response.delete_cookie(
            key=cookies.session_name,
            path="/",
            secure=cookies.secure,
            httponly=True,
            samesite="lax",
        )
        response.delete_cookie(
            key=cookies.csrf_name,
            path="/",
            secure=cookies.secure,
            httponly=False,
            samesite="lax",
        )
        return response

    @app.post(
        "/api/v1/auth/session/reauthentications",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )
    async def reauthenticate_browser_session(
        payload: BrowserSessionReauthenticationRequest, request: Request
    ) -> Response:
        await enforce_auth_rate_limit(request, scope="auth.reauthentication")
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        assurance_level = getattr(request.state, "assurance_level", None)
        authenticated_at = getattr(request.state, "authenticated_at", None)
        if (
            not isinstance(actor_id, UUID)
            or not isinstance(session_id, UUID)
            or not isinstance(assurance_level, SessionAssuranceLevel)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if session_reauthentication_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session reauthentication is unavailable",
            )
        try:
            await session_reauthentication_use_case.execute(
                ReauthenticateBrowserSessionCommand(
                    principal=BrowserSessionPrincipal(
                        user_id=actor_id,
                        session_id=session_id,
                        assurance_level=assurance_level,
                        authenticated_at=authenticated_at,
                    ),
                    current_password=payload.current_password.get_secret_value(),
                    correlation_id=request.state.correlation_id,
                )
            )
        except BrowserSessionReauthenticationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session reauthentication failed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/auth/identities",
        response_model=LoginIdentityListResponse,
        tags=["authentication"],
    )
    async def list_login_identities(request: Request) -> LoginIdentityListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if login_identity_list_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login identity listing is unavailable",
            )
        try:
            identities = await login_identity_list_use_case.execute(
                ListLoginIdentitiesCommand(
                    actor_id=actor_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except LoginIdentityManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return LoginIdentityListResponse(
            items=[
                _login_identity_response(identity, total_identity_count=len(identities))
                for identity in identities
            ]
        )

    @app.delete(
        "/api/v1/auth/identities/{identity_id}",
        response_model=LoginIdentityResponse,
        tags=["authentication"],
    )
    async def unlink_login_identity(identity_id: UUID, request: Request) -> LoginIdentityResponse:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        assurance_level = getattr(request.state, "assurance_level", None)
        authenticated_at = getattr(request.state, "authenticated_at", None)
        if (
            not isinstance(actor_id, UUID)
            or not isinstance(session_id, UUID)
            or not isinstance(assurance_level, SessionAssuranceLevel)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if login_identity_unlink_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login identity unlink is unavailable",
            )
        try:
            identity = await login_identity_unlink_use_case.execute(
                UnlinkLoginIdentityCommand(
                    principal=BrowserSessionPrincipal(
                        user_id=actor_id,
                        session_id=session_id,
                        assurance_level=assurance_level,
                        authenticated_at=authenticated_at,
                    ),
                    identity_id=identity_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except RecentAuthenticationRequiredError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent authentication is required",
            ) from error
        except LoginIdentityManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Login identity unlink failed",
            ) from error
        return _login_identity_response(identity, total_identity_count=0)

    @app.put(
        "/api/v1/auth/password",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )
    async def change_email_password(payload: PasswordChangeRequest, request: Request) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        assurance_level = getattr(request.state, "assurance_level", None)
        authenticated_at = getattr(request.state, "authenticated_at", None)
        if (
            not isinstance(actor_id, UUID)
            or not isinstance(session_id, UUID)
            or not isinstance(assurance_level, SessionAssuranceLevel)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if password_change_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password change is unavailable",
            )
        try:
            await password_change_use_case.execute(
                ChangeEmailPasswordCommand(
                    principal=BrowserSessionPrincipal(
                        user_id=actor_id,
                        session_id=session_id,
                        assurance_level=assurance_level,
                        authenticated_at=authenticated_at,
                    ),
                    current_password=payload.current_password.get_secret_value(),
                    new_password=payload.new_password.get_secret_value(),
                    correlation_id=request.state.correlation_id,
                )
            )
        except RecentAuthenticationRequiredError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent authentication is required",
            ) from error
        except PasswordChangeRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password change failed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/auth/password-recovery/requests",
        response_model=PasswordRecoveryRequestResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["authentication"],
    )
    async def request_password_recovery(
        payload: PasswordRecoveryRequest, request: Request
    ) -> PasswordRecoveryRequestResponse:
        await enforce_auth_rate_limit(request, scope="auth.password_recovery.request")
        if password_recovery_request_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password recovery is unavailable",
            )
        try:
            await password_recovery_request_use_case.execute(
                RequestPasswordRecoveryCommand(
                    email=str(payload.email),
                    correlation_id=request.state.correlation_id,
                )
            )
        except ConnectionError as error:
            logger.error(
                "password.recovery.request.backend_unavailable",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password recovery is temporarily unavailable",
            ) from error
        return PasswordRecoveryRequestResponse()

    async def begin_external_identity_link(
        *,
        request: Request,
        provider: LoginIdentityProvider,
        start_use_case: BeginIdentityLink | None,
        authorization_url: Callable[..., str] | None,
        provider_label: str,
    ) -> dict[str, str | int]:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if start_use_case is None or authorization_url is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_label} identity linking is unavailable",
            )
        try:
            started = await start_use_case.execute(
                BeginIdentityLinkCommand(
                    actor_id=actor_id,
                    provider=provider,
                    correlation_id=request.state.correlation_id,
                )
            )
            logger.info(
                "identity.link.authorization_started",
                extra={
                    "provider": provider.value,
                    "actor_id": str(actor_id),
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            return {
                "authorization_url": authorization_url(
                    state=started.state, code_challenge=started.code_challenge
                ),
                "expires_in_seconds": started.expires_in_seconds,
            }
        except IdentityLinkStartRejectedError as error:
            logger.warning(
                "identity.link.authorization_rejected",
                extra={
                    "provider": provider.value,
                    "actor_id": str(actor_id),
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{provider_label} identity linking failed",
            ) from error

    async def begin_oauth_login(
        *,
        request: Request,
        provider: LoginIdentityProvider,
        start_use_case: BeginOAuthLogin | None,
        authorization_url: Callable[..., str] | None,
        provider_label: str,
    ) -> dict[str, str | int]:
        """Start one provider-neutral, rate-limited OAuth login transaction."""
        await enforce_auth_rate_limit(request, scope="auth.oauth.start")
        if start_use_case is None or authorization_url is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_label} sign-in is unavailable",
            )
        try:
            started = await start_use_case.execute(
                provider=provider,
                correlation_id=request.state.correlation_id,
            )
        except OAuthLoginStartRejectedError as error:
            logger.warning(
                "auth.oauth_login.start.rejected",
                extra={
                    "provider": provider.value,
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_label} sign-in is unavailable",
            ) from error
        logger.info(
            "auth.oauth_login.authorization_started",
            extra={
                "provider": provider.value,
                "correlation_id": str(request.state.correlation_id),
            },
        )
        return {
            "authorization_url": authorization_url(
                state=started.state, code_challenge=started.code_challenge
            ),
            "expires_in_seconds": started.expires_in_seconds,
        }

    async def complete_oauth_login_if_valid(
        *,
        request: Request,
        provider: LoginIdentityProvider,
        state: str,
        authorization_code: str,
        completion: CompleteOAuthLogin | None,
    ) -> IssuedBrowserSession | None:
        """Try the login transaction before falling back to identity linking."""
        if completion is None:
            return None
        try:
            return await completion.execute(
                provider=provider,
                state=state,
                authorization_code=authorization_code,
                correlation_id=request.state.correlation_id,
                client_ip=_request_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
        except OAuthLoginCompletionRejectedError:
            logger.info(
                "auth.oauth_login.callback_not_a_login_transaction",
                extra={
                    "provider": provider.value,
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            return None

    async def complete_external_identity_link_callback(
        *,
        request: Request,
        provider: LoginIdentityProvider,
        state: str,
        authorization_code: str,
        login_completion: CompleteOAuthLogin | None,
        identity_link_completion: CompleteIdentityLink | None,
        provider_label: str,
    ) -> Response:
        """Complete login first, then safely fall back to identity linking."""
        await enforce_auth_rate_limit(request, scope="auth.oauth.callback")
        issued_session = await complete_oauth_login_if_valid(
            request=request,
            provider=provider,
            state=state,
            authorization_code=authorization_code,
            completion=login_completion,
        )
        if issued_session is not None:
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            _set_browser_session_cookies(response, issued_session, cookies)
            return response
        if identity_link_completion is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_label} identity linking is unavailable",
            )
        try:
            await identity_link_completion.execute(
                CompleteIdentityLinkCommand(
                    provider=provider,
                    state=state,
                    authorization_code=authorization_code,
                    correlation_id=request.state.correlation_id,
                )
            )
            logger.info(
                "identity.link.callback_completed",
                extra={
                    "provider": provider.value,
                    "correlation_id": str(request.state.correlation_id),
                },
            )
        except IdentityLinkCompletionRejectedError as error:
            logger.warning(
                "identity.link.callback_rejected",
                extra={
                    "provider": provider.value,
                    "correlation_id": str(request.state.correlation_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{provider_label} identity linking failed",
            ) from error
        return RedirectResponse(
            url=f"/?identity_linked={provider.value}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.post(
        "/api/v1/auth/password-recovery/completions",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )
    async def complete_password_recovery(
        payload: PasswordRecoveryCompletionRequest, request: Request
    ) -> Response:
        await enforce_auth_rate_limit(request, scope="auth.password_recovery.complete")
        if password_recovery_completion_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password recovery is unavailable",
            )
        try:
            await password_recovery_completion_use_case.execute(
                CompletePasswordRecoveryCommand(
                    token=payload.token.get_secret_value(),
                    new_password=payload.new_password.get_secret_value(),
                    correlation_id=request.state.correlation_id,
                )
            )
        except ConnectionError as error:
            logger.error(
                "password.recovery.complete.backend_unavailable",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password recovery is temporarily unavailable",
            ) from error
        except PasswordRecoveryCompletionRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password recovery failed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/organizations/{organization_id}/audit-events",
        response_model=AuditEventListResponse,
        tags=["audit-events"],
    )
    async def list_organization_audit_events(
        organization_id: UUID, request: Request, after: UUID | None = None, limit: int = 50
    ) -> AuditEventListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if audit_events_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization audit events are unavailable",
            )
        try:
            page = await audit_events_use_case.execute(
                actor_id=actor_id, organization_id=organization_id, after_id=after, limit=limit
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return AuditEventListResponse(
            items=[
                AuditEventResponse(
                    id=str(entry.id),
                    correlation_id=str(entry.correlation_id),
                    actor_id=str(entry.actor_id) if entry.actor_id else None,
                    action=entry.action,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    result=entry.result,
                    created_at=entry.created_at,
                )
                for entry in page.items
            ],
            next_cursor=str(page.next_cursor) if page.next_cursor else None,
        )

    @app.post(
        "/api/v1/identity-links/discord/authorizations",
        tags=["identity-links"],
    )
    async def begin_discord_identity_link(request: Request) -> dict[str, str | int]:
        return await begin_external_identity_link(
            request=request,
            provider=LoginIdentityProvider.DISCORD,
            start_use_case=discord_identity_link_start,
            authorization_url=discord_authorization_url,
            provider_label="Discord",
        )

    @app.post(
        "/api/v1/identity-links/twitch/authorizations",
        tags=["identity-links"],
    )
    async def begin_twitch_identity_link(request: Request) -> dict[str, str | int]:
        return await begin_external_identity_link(
            request=request,
            provider=LoginIdentityProvider.TWITCH,
            start_use_case=twitch_identity_link_start,
            authorization_url=twitch_authorization_url,
            provider_label="Twitch",
        )

    @app.post(
        "/api/v1/identity-links/google/authorizations",
        tags=["identity-links"],
    )
    async def begin_google_identity_link(request: Request) -> dict[str, str | int]:
        return await begin_external_identity_link(
            request=request,
            provider=LoginIdentityProvider.GOOGLE,
            start_use_case=google_identity_link_start,
            authorization_url=google_authorization_url,
            provider_label="Google",
        )

    @app.post(
        "/api/v1/identity-links/yandex/authorizations",
        tags=["identity-links"],
    )
    async def begin_yandex_identity_link(request: Request) -> dict[str, str | int]:
        return await begin_external_identity_link(
            request=request,
            provider=LoginIdentityProvider.YANDEX,
            start_use_case=yandex_identity_link_start,
            authorization_url=yandex_authorization_url,
            provider_label="Yandex ID",
        )

    @app.post(
        "/api/v1/identity-links/telegram/authorizations",
        tags=["identity-links"],
    )
    async def begin_telegram_identity_link(request: Request) -> dict[str, str | int]:
        return await begin_external_identity_link(
            request=request,
            provider=LoginIdentityProvider.TELEGRAM,
            start_use_case=telegram_identity_link_start,
            authorization_url=telegram_authorization_url,
            provider_label="Telegram",
        )

    @app.get(
        "/api/v1/auth/providers",
        response_model=OAuthProviderCatalogResponse,
        tags=["authentication"],
    )
    async def list_oauth_providers(request: Request) -> OAuthProviderCatalogResponse:
        providers = [
            provider.value
            for provider, start_use_case, authorization_url in (
                (
                    LoginIdentityProvider.DISCORD,
                    discord_login_start,
                    discord_authorization_url,
                ),
                (
                    LoginIdentityProvider.TWITCH,
                    twitch_login_start,
                    twitch_authorization_url,
                ),
                (
                    LoginIdentityProvider.TELEGRAM,
                    telegram_login_start,
                    telegram_authorization_url,
                ),
                (
                    LoginIdentityProvider.GOOGLE,
                    google_login_start,
                    google_authorization_url,
                ),
                (
                    LoginIdentityProvider.YANDEX,
                    yandex_login_start,
                    yandex_authorization_url,
                ),
            )
            if start_use_case is not None and authorization_url is not None
        ]
        logger.info(
            "auth.oauth_login.providers_listed",
            extra={
                "providers": providers,
                "correlation_id": str(request.state.correlation_id),
            },
        )
        return OAuthProviderCatalogResponse(providers=providers)

    @app.post("/api/v1/auth/discord/authorizations", tags=["authentication"])
    async def begin_discord_oauth_login(request: Request) -> dict[str, str | int]:
        return await begin_oauth_login(
            request=request,
            provider=LoginIdentityProvider.DISCORD,
            start_use_case=discord_login_start,
            authorization_url=discord_authorization_url,
            provider_label="Discord",
        )

    @app.post("/api/v1/auth/twitch/authorizations", tags=["authentication"])
    async def begin_twitch_oauth_login(request: Request) -> dict[str, str | int]:
        return await begin_oauth_login(
            request=request,
            provider=LoginIdentityProvider.TWITCH,
            start_use_case=twitch_login_start,
            authorization_url=twitch_authorization_url,
            provider_label="Twitch",
        )

    @app.post("/api/v1/auth/telegram/authorizations", tags=["authentication"])
    async def begin_telegram_oauth_login(request: Request) -> dict[str, str | int]:
        return await begin_oauth_login(
            request=request,
            provider=LoginIdentityProvider.TELEGRAM,
            start_use_case=telegram_login_start,
            authorization_url=telegram_authorization_url,
            provider_label="Telegram",
        )

    @app.post("/api/v1/auth/google/authorizations", tags=["authentication"])
    async def begin_google_oauth_login(request: Request) -> dict[str, str | int]:
        return await begin_oauth_login(
            request=request,
            provider=LoginIdentityProvider.GOOGLE,
            start_use_case=google_login_start,
            authorization_url=google_authorization_url,
            provider_label="Google",
        )

    @app.post("/api/v1/auth/yandex/authorizations", tags=["authentication"])
    async def begin_yandex_oauth_login(request: Request) -> dict[str, str | int]:
        return await begin_oauth_login(
            request=request,
            provider=LoginIdentityProvider.YANDEX,
            start_use_case=yandex_login_start,
            authorization_url=yandex_authorization_url,
            provider_label="Yandex ID",
        )

    @app.get("/api/v1/auth/discord/callback", tags=["authentication"])
    @app.get("/api/v1/identity-links/discord/callback", tags=["identity-links"])
    async def complete_discord_oauth_callback(code: str, state: str, request: Request) -> Response:
        return await complete_external_identity_link_callback(
            request=request,
            provider=LoginIdentityProvider.DISCORD,
            state=state,
            authorization_code=code,
            login_completion=discord_login_complete,
            identity_link_completion=discord_identity_link_complete,
            provider_label="Discord",
        )

    @app.get("/api/v1/auth/twitch/callback", tags=["authentication", "identity-links"])
    @app.get("/api/v1/identity-links/twitch/callback", tags=["identity-links"])
    async def complete_twitch_identity_link_callback(
        code: str, state: str, request: Request
    ) -> Response:
        return await complete_external_identity_link_callback(
            request=request,
            provider=LoginIdentityProvider.TWITCH,
            state=state,
            authorization_code=code,
            login_completion=twitch_login_complete,
            identity_link_completion=twitch_identity_link_complete,
            provider_label="Twitch",
        )

    @app.get("/api/v1/auth/google/callback", tags=["authentication"])
    @app.get("/api/v1/identity-links/google/callback", tags=["identity-links"])
    async def complete_google_oauth_callback(code: str, state: str, request: Request) -> Response:
        return await complete_external_identity_link_callback(
            request=request,
            provider=LoginIdentityProvider.GOOGLE,
            state=state,
            authorization_code=code,
            login_completion=google_login_complete,
            identity_link_completion=google_identity_link_complete,
            provider_label="Google",
        )

    @app.get("/api/v1/auth/yandex/callback", tags=["authentication"])
    @app.get("/api/v1/identity-links/yandex/callback", tags=["identity-links"])
    async def complete_yandex_oauth_callback(code: str, state: str, request: Request) -> Response:
        return await complete_external_identity_link_callback(
            request=request,
            provider=LoginIdentityProvider.YANDEX,
            state=state,
            authorization_code=code,
            login_completion=yandex_login_complete,
            identity_link_completion=yandex_identity_link_complete,
            provider_label="Yandex ID",
        )

    @app.get("/api/v1/auth/telegram/callback", tags=["authentication"])
    @app.get("/api/v1/identity-links/telegram/callback", tags=["identity-links"])
    async def complete_telegram_oauth_callback(code: str, state: str, request: Request) -> Response:
        return await complete_external_identity_link_callback(
            request=request,
            provider=LoginIdentityProvider.TELEGRAM,
            state=state,
            authorization_code=code,
            login_completion=telegram_login_complete,
            identity_link_completion=telegram_identity_link_complete,
            provider_label="Telegram",
        )

    @app.get(
        "/api/v1/organizations",
        response_model=OrganizationListResponse,
        tags=["organizations"],
    )
    async def list_organizations(request: Request) -> OrganizationListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_list_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization listing is unavailable",
            )
        try:
            profiles = await organization_list_use_case.execute(
                ListOrganizationsCommand(
                    actor_id=actor_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationListRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return OrganizationListResponse(
            items=[
                OrganizationListItemResponse(
                    organization=OrganizationResponse.model_validate(
                        profile.organization, from_attributes=True
                    ),
                    membership=_membership_response(profile.membership),
                )
                for profile in profiles
            ]
        )

    @app.post(
        "/api/v1/organizations",
        response_model=OrganizationResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["organizations"],
    )
    async def create_organization(
        payload: OrganizationCreateRequest, request: Request
    ) -> OrganizationResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_creation_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization creation is unavailable",
            )
        try:
            organization = await organization_creation_use_case.execute(
                CreateOrganizationCommand(
                    actor_id=actor_id,
                    name=payload.name,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationCreationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization creation failed"
            ) from error
        return OrganizationResponse.model_validate(organization, from_attributes=True)

    @app.get(
        "/api/v1/organizations/{organization_id}/members",
        response_model=OrganizationMemberListResponse,
        tags=["organization-members"],
    )
    async def list_organization_members(
        organization_id: UUID, request: Request
    ) -> OrganizationMemberListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_members_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization members are unavailable",
            )
        try:
            members = await organization_members_use_case.execute(
                ListOrganizationMembersCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationMemberManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return OrganizationMemberListResponse(
            items=[_organization_member_response(member) for member in members]
        )

    @app.post(
        "/api/v1/organizations/{organization_id}/members",
        response_model=OrganizationMembershipResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["organization-members"],
    )
    async def add_organization_member(
        organization_id: UUID, payload: OrganizationMemberCreateRequest, request: Request
    ) -> OrganizationMembershipResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_member_add_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization member creation is unavailable",
            )
        try:
            membership = await organization_member_add_use_case.execute(
                AddOrganizationMemberCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    email=str(payload.email),
                    role=payload.role,
                    resource_scopes=_scope_requests_to_domain(payload.resource_scopes),
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationMemberManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization member creation failed",
            ) from error
        return _membership_response(membership)

    @app.put(
        "/api/v1/organizations/{organization_id}/members/{user_id}",
        response_model=OrganizationMembershipResponse,
        tags=["organization-members"],
    )
    async def update_organization_member(
        organization_id: UUID,
        user_id: UUID,
        payload: OrganizationMemberUpdateRequest,
        request: Request,
    ) -> OrganizationMembershipResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_member_update_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization member update is unavailable",
            )
        try:
            membership = await organization_member_update_use_case.execute(
                UpdateOrganizationMemberCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    role=payload.role,
                    resource_scopes=_scope_requests_to_domain(payload.resource_scopes),
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationMemberManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization member update failed",
            ) from error
        return _membership_response(membership)

    @app.delete(
        "/api/v1/organizations/{organization_id}/members/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["organization-members"],
    )
    async def remove_organization_member(
        organization_id: UUID, user_id: UUID, request: Request
    ) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_member_remove_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization member removal is unavailable",
            )
        try:
            await organization_member_remove_use_case.execute(
                RemoveOrganizationMemberCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationMemberManagementRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization member removal failed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/organizations/{organization_id}/member-invitations",
        response_model=OrganizationInvitationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["organization-members"],
    )
    async def create_organization_member_invitation(
        organization_id: UUID, payload: OrganizationInvitationCreateRequest, request: Request
    ) -> OrganizationInvitationResponse:
        await enforce_auth_rate_limit(request, scope="organization.invitation.create")
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_invitation_create_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization invitations are unavailable",
            )
        try:
            result = await organization_invitation_create_use_case.execute(
                InviteOrganizationMemberCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    email=str(payload.email),
                    role=payload.role,
                    resource_scopes=_scope_requests_to_domain(payload.resource_scopes),
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationInvitationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization invitation could not be created",
            ) from error
        return _organization_invitation_response(
            result.invitation,
            now=datetime.now(UTC),
            delivery_status=result.delivery_status,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/member-invitations",
        response_model=OrganizationInvitationListResponse,
        tags=["organization-members"],
    )
    async def list_organization_member_invitations(
        organization_id: UUID, request: Request
    ) -> OrganizationInvitationListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_invitation_list_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization invitations are unavailable",
            )
        try:
            invitations = await organization_invitation_list_use_case.execute(
                ListOrganizationInvitationsCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationInvitationListingRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        now = datetime.now(UTC)
        return OrganizationInvitationListResponse(
            items=[
                _organization_invitation_response(invitation, now=now) for invitation in invitations
            ]
        )

    @app.delete(
        "/api/v1/organizations/{organization_id}/member-invitations/{invitation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["organization-members"],
    )
    async def revoke_organization_member_invitation(
        organization_id: UUID, invitation_id: UUID, request: Request
    ) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_invitation_revoke_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization invitations are unavailable",
            )
        try:
            await organization_invitation_revoke_use_case.execute(
                RevokeOrganizationInvitationCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    invitation_id=invitation_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationInvitationRevocationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization invitation revocation failed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/member-invitations/accept",
        response_model=OrganizationMembershipResponse,
        tags=["organization-members"],
    )
    async def accept_organization_member_invitation(
        payload: OrganizationInvitationAcceptRequest, request: Request
    ) -> OrganizationMembershipResponse:
        await enforce_auth_rate_limit(request, scope="auth.invitation.accept")
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if organization_invitation_accept_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Organization invitation acceptance is unavailable",
            )
        try:
            membership = await organization_invitation_accept_use_case.execute(
                AcceptOrganizationInvitationCommand(
                    actor_id=actor_id,
                    raw_token=payload.token,
                    correlation_id=request.state.correlation_id,
                )
            )
        except OrganizationInvitationAcceptanceRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization invitation acceptance failed",
            ) from error
        return _membership_response(membership)

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connection-candidates",
        response_model=PlatformConnectionCandidateListResponse,
        tags=["platform-connections"],
    )
    async def list_platform_connection_candidates(
        organization_id: UUID, platform: Platform, request: Request, response: Response
    ) -> PlatformConnectionCandidateListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        response.headers["Cache-Control"] = "no-store"
        if platform_connection_candidates_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform connection candidate discovery is unavailable",
            )
        try:
            catalog = await platform_connection_candidates_use_case.execute(
                ListPlatformConnectionCandidatesCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    platform=platform,
                    correlation_id=request.state.correlation_id,
                )
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return _platform_connection_candidate_response(catalog)

    @app.post(
        "/api/v1/organizations/{organization_id}/platform-connections",
        response_model=PlatformConnectionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["platform-connections"],
    )
    async def connect_platform_connection(
        organization_id: UUID, payload: PlatformConnectionCreateRequest, request: Request
    ) -> PlatformConnectionResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_connection_connect_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform connection setup is unavailable",
            )
        try:
            connection = await platform_connection_connect_use_case.execute(
                ConnectPlatformConnectionCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    platform=payload.platform,
                    external_resource_id=payload.external_resource_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except PlatformConnectionConnectRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform connection setup failed",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return _platform_connection_response(connection)

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections",
        response_model=PlatformConnectionListResponse,
        tags=["platform-connections"],
    )
    async def list_platform_connections(
        organization_id: UUID,
        request: Request,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> PlatformConnectionListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_connections_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform connections are unavailable",
            )
        try:
            page = await platform_connections_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                after_id=cursor,
                limit=limit,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        return PlatformConnectionListResponse(
            items=[_platform_connection_response(connection) for connection in page.items],
            next_cursor=page.next_cursor,
        )

    async def run_platform_connection_lifecycle(
        *,
        organization_id: UUID,
        connection_id: UUID,
        action: PlatformConnectionLifecycleAction,
        request: Request,
    ) -> PlatformConnectionResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_connection_lifecycle_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform connection lifecycle is unavailable",
            )
        try:
            connection = await platform_connection_lifecycle_use_case.execute(
                ManagePlatformConnectionLifecycleCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    connection_id=connection_id,
                    action=action,
                    correlation_id=request.state.correlation_id,
                    idempotency_key=request.headers.get("Idempotency-Key"),
                )
            )
        except PlatformConnectionLifecycleRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform connection lifecycle action failed",
            ) from error
        return _platform_connection_response(connection)

    @app.post(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/reauthorizations",
        response_model=PlatformConnectionResponse,
        tags=["platform-connections"],
    )
    async def reauthorize_platform_connection(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformConnectionResponse:
        return await run_platform_connection_lifecycle(
            organization_id=organization_id,
            connection_id=connection_id,
            action=PlatformConnectionLifecycleAction.REAUTHORIZE,
            request=request,
        )

    @app.post(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/revocations",
        response_model=PlatformConnectionResponse,
        tags=["platform-connections"],
    )
    async def revoke_platform_connection(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformConnectionResponse:
        return await run_platform_connection_lifecycle(
            organization_id=organization_id,
            connection_id=connection_id,
            action=PlatformConnectionLifecycleAction.REVOKE,
            request=request,
        )

    @app.delete(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}",
        response_model=PlatformConnectionResponse,
        tags=["platform-connections"],
    )
    async def disconnect_platform_connection(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformConnectionResponse:
        return await run_platform_connection_lifecycle(
            organization_id=organization_id,
            connection_id=connection_id,
            action=PlatformConnectionLifecycleAction.DISCONNECT,
            request=request,
        )

    @app.post(
        "/api/v1/auth/email-password/registrations",
        response_model=EmailPasswordRegistrationResponse,
        response_model_exclude_none=True,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["authentication"],
    )
    async def start_email_password_registration(
        payload: EmailPasswordRegistrationRequest, request: Request
    ) -> EmailPasswordRegistrationResponse:
        await enforce_auth_rate_limit(request, scope="auth.registration")
        if registration_verification_start_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registration is unavailable",
            )
        try:
            started = await registration_verification_start_use_case.execute(
                StartEmailPasswordRegistrationCommand(
                    email=str(payload.email),
                    password=payload.password.get_secret_value(),
                    display_name=payload.display_name,
                    correlation_id=request.state.correlation_id,
                )
            )
        except (ConnectionError, ValueError) as error:
            logger.error(
                "auth.email_password.verification.start_failed",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            if isinstance(error, ConnectionError):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Registration is temporarily unavailable",
                ) from error
            # Keep malformed application input generic even if a future
            # contract stops validating it at the Pydantic boundary.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Registration data is invalid",
            ) from error
        return EmailPasswordRegistrationResponse(
            status="verification_required",
            verification_token=started.raw_token,
        )

    @app.post(
        "/api/v1/auth/email-password/registration-verifications",
        response_model=EmailPasswordRegistrationVerificationResponse,
        status_code=status.HTTP_200_OK,
        tags=["authentication"],
    )
    async def verify_email_password_registration(
        payload: EmailPasswordRegistrationVerificationRequest, request: Request
    ) -> EmailPasswordRegistrationVerificationResponse:
        await enforce_auth_rate_limit(request, scope="auth.registration.verification")
        if registration_verification_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="E-mail verification is unavailable",
            )
        try:
            await registration_verification_use_case.execute(
                VerifyEmailPasswordRegistrationCommand(
                    token=payload.token.get_secret_value(),
                    code=payload.code,
                    correlation_id=request.state.correlation_id,
                )
            )
        except EmailPasswordRegistrationVerificationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="E-mail verification failed",
            ) from error
        except ConnectionError as error:
            logger.error(
                "auth.email_password.verification.backend_unavailable",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="E-mail verification is temporarily unavailable",
            ) from error
        return EmailPasswordRegistrationVerificationResponse()

    @app.post(
        "/api/v1/auth/email-password/registration-verifications/resend",
        response_model=EmailPasswordRegistrationResponse,
        response_model_exclude_none=True,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["authentication"],
    )
    async def resend_email_password_registration_verification(
        payload: EmailPasswordRegistrationVerificationResendRequest, request: Request
    ) -> EmailPasswordRegistrationResponse:
        await enforce_auth_rate_limit(request, scope="auth.registration.resend")
        if registration_verification_start_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="E-mail verification is unavailable",
            )
        try:
            resent = await registration_verification_start_use_case.resend(
                ResendEmailPasswordRegistrationCommand(
                    token=payload.token.get_secret_value(),
                    correlation_id=request.state.correlation_id,
                )
            )
        except ConnectionError as error:
            logger.error(
                "auth.email_password.verification.resend_backend_unavailable",
                extra={
                    "correlation_id": str(request.state.correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="E-mail verification is temporarily unavailable",
            ) from error
        return EmailPasswordRegistrationResponse(
            status="verification_required",
            verification_token=resent.raw_token,
        )

    @app.post(
        "/api/v1/auth/email-password/sessions",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )
    async def authenticate_email_password(
        payload: EmailPasswordLoginRequest, request: Request
    ) -> Response:
        await enforce_auth_rate_limit(request, scope="auth.login")
        if authentication_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is unavailable",
            )
        try:
            issued_session = await authentication_use_case.execute(
                AuthenticateEmailPasswordCommand(
                    email=str(payload.email),
                    password=payload.password.get_secret_value(),
                    correlation_id=request.state.correlation_id,
                    client_ip=_request_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                )
            )
        except AuthenticationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            ) from error

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        _set_browser_session_cookies(response, issued_session, cookies)
        return response

    @app.get(
        "/api/v1/organizations/{organization_id}/control-modules",
        response_model=ControlModuleListResponse,
        tags=["control-modules"],
    )
    async def list_control_modules(
        organization_id: UUID, request: Request
    ) -> ControlModuleListResponse:
        # Authentication will set this state from a first-party browser session.
        # A missing principal is deliberately indistinguishable from insufficient access.
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        try:
            modules = await control_modules.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return ControlModuleListResponse(
            organization_id=organization_id,
            items=[
                ControlModuleResponse.model_validate(module, from_attributes=True)
                for module in modules
            ],
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platforms/{platform}/health",
        response_model=PlatformHealthResponse,
        tags=["platform-health"],
    )
    async def get_platform_health(
        organization_id: UUID, platform: Platform, request: Request
    ) -> PlatformHealthResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_health_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform health is unavailable",
            )
        try:
            health = await platform_health_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                platform=platform,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform health is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformHealthResponse(
            organization_id=str(organization_id),
            platform=health.platform,
            signals=[
                HealthSignalResponse.model_validate(signal, from_attributes=True)
                for signal in health.signals
            ],
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/dashboard",
        response_model=PlatformDashboardSummaryResponse,
        tags=["platform-dashboard"],
    )
    async def get_platform_dashboard_summary(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformDashboardSummaryResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_dashboard_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform dashboard is unavailable",
            )
        try:
            summary = await platform_dashboard_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform dashboard is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformDashboardSummaryResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=summary.platform,
            messages_today=summary.messages_today,
            ai_flagged_today=summary.ai_flagged_today,
            creator_sources=summary.creator_sources,
            bot_latency_ms=summary.bot_latency_ms,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/bot-settings",
        response_model=PlatformBotSettingsResponse,
        tags=["platform-bot-settings"],
    )
    async def get_platform_bot_settings(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformBotSettingsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_bot_settings_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform bot settings are unavailable",
            )
        try:
            settings = await platform_bot_settings_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform bot settings are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformBotSettingsResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=settings.platform,
            subscription_tier=settings.subscription_tier,
            activity_rotation_enabled=settings.activity_rotation_enabled,
            activity_rotation_interval_seconds=settings.activity_rotation_interval_seconds,
            retention_days=dict(settings.retention_days),
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/audit-timeline",
        response_model=PlatformAuditTimelineResponse,
        tags=["platform-audit-timeline"],
    )
    async def get_platform_audit_timeline(
        organization_id: UUID,
        connection_id: UUID,
        request: Request,
    ) -> PlatformAuditTimelineResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_audit_timeline_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform audit timeline is unavailable",
            )
        try:
            timeline = await platform_audit_timeline_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform audit timeline is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformAuditTimelineResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=timeline.platform,
            items=[
                {"event_type": event.event_type, "occurred_at": event.occurred_at}
                for event in timeline.events
            ],
            limit=timeline.limit,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/server-statistics",
        response_model=PlatformServerStatisticsResponse,
        tags=["platform-server-statistics"],
    )
    async def get_platform_server_statistics(
        organization_id: UUID,
        connection_id: UUID,
        request: Request,
    ) -> PlatformServerStatisticsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_server_statistics_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform server statistics are unavailable",
            )
        try:
            statistics = await platform_server_statistics_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform server statistics are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformServerStatisticsResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=statistics.platform,
            period_days=statistics.period_days,
            total_messages=statistics.total_messages,
            active_users=statistics.active_users,
            active_channels=statistics.active_channels,
            current_member_count=statistics.current_member_count,
            total_voice_minutes=statistics.total_voice_minutes,
            joins=statistics.joins,
            leaves=statistics.leaves,
            net_member_growth=statistics.joins - statistics.leaves,
            moderation_events=statistics.moderation_events,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/integrations",
        response_model=PlatformIntegrationsResponse,
        tags=["platform-integrations"],
    )
    async def get_platform_integrations(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformIntegrationsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_integrations_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform integrations are unavailable",
            )
        try:
            integrations = await platform_integrations_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform integrations are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformIntegrationsResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=integrations.platform,
            discord_bot_status=integrations.discord_bot_status,
            creator_platforms_status=integrations.creator_platforms_status,
            creator_poll_interval_seconds=integrations.creator_poll_interval_seconds,
            creator_sources=[
                {"platform": item.platform, "total": item.total, "active": item.active}
                for item in integrations.creator_sources
            ],
            muxivo_core_status=integrations.muxivo_core_status,
            database_status=integrations.database_status,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/channels",
        response_model=PlatformChannelCatalogResponse,
        tags=["platform-channels"],
    )
    async def list_platform_connection_channels(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformChannelCatalogResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_channels_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform channels are unavailable",
            )
        try:
            catalog = await platform_channels_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform channels are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformChannelCatalogResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=catalog.platform,
            items=[
                PlatformChannelResponse.model_validate(item, from_attributes=True)
                for item in catalog.items
            ],
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/channel-purposes",
        response_model=PlatformChannelPurposesResponse,
        tags=["platform-channel-purposes"],
    )
    async def get_platform_channel_purposes(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformChannelPurposesResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_channel_purposes_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform channel purposes are unavailable",
            )
        try:
            purposes = await platform_channel_purposes_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform channel purposes are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformChannelPurposesResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=purposes.platform,
            items=[
                ChannelPurposeAssignmentResponse(purpose=purpose, channel_id=channel_id)
                for purpose, channel_id in purposes.assignments.items()
            ],
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/ai-moderation-summary",
        response_model=PlatformAiModerationSummaryResponse,
        tags=["platform-ai-moderation"],
    )
    async def get_platform_ai_moderation_summary(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformAiModerationSummaryResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_ai_moderation_summary_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform AI moderation summary is unavailable",
            )
        try:
            summary = await platform_ai_moderation_summary_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform AI moderation summary is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformAiModerationSummaryResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=summary.platform,
            enforcement_mode=summary.enforcement_mode,
            test_mode=summary.test_mode,
            is_default_policy=summary.is_default_policy,
            covered_channel_count=summary.covered_channel_count,
            log_channel_configured=summary.log_channel_configured,
            label_count=summary.label_count,
            blacklist_word_count=summary.blacklist_word_count,
            allowed_domain_count=summary.allowed_domain_count,
            automated_timeout_enabled=summary.automated_timeout_enabled,
            automated_kick_enabled=summary.automated_kick_enabled,
            automated_ban_enabled=summary.automated_ban_enabled,
        )

    @app.put(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/ai-moderation-policy",
        response_model=PlatformAiModerationSummaryResponse,
        tags=["platform-ai-moderation"],
    )
    async def update_platform_ai_moderation_policy(
        organization_id: UUID,
        connection_id: UUID,
        payload: AiModerationPolicyUpdateRequest,
        request: Request,
    ) -> PlatformAiModerationSummaryResponse:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        assurance_level = getattr(request.state, "assurance_level", None)
        authenticated_at = getattr(request.state, "authenticated_at", None)
        if (
            not isinstance(actor_id, UUID)
            or not isinstance(session_id, UUID)
            or not isinstance(assurance_level, SessionAssuranceLevel)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_ai_moderation_policy_update_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform AI moderation policy is unavailable",
            )
        try:
            summary = await platform_ai_moderation_policy_update_use_case.execute(
                principal=BrowserSessionPrincipal(
                    user_id=actor_id,
                    session_id=session_id,
                    assurance_level=assurance_level,
                    authenticated_at=authenticated_at,
                ),
                organization_id=organization_id,
                connection_id=connection_id,
                policy=payload.to_domain_policy(),
                correlation_id=request.state.correlation_id,
            )
        except RecentAuthenticationRequiredError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent authentication is required",
            ) from error
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform AI moderation policy is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformAiModerationSummaryResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=summary.platform,
            enforcement_mode=summary.enforcement_mode,
            test_mode=summary.test_mode,
            is_default_policy=summary.is_default_policy,
            covered_channel_count=summary.covered_channel_count,
            log_channel_configured=summary.log_channel_configured,
            label_count=summary.label_count,
            blacklist_word_count=summary.blacklist_word_count,
            allowed_domain_count=summary.allowed_domain_count,
            automated_timeout_enabled=summary.automated_timeout_enabled,
            automated_kick_enabled=summary.automated_kick_enabled,
            automated_ban_enabled=summary.automated_ban_enabled,
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/ai-moderation-policy",
        response_model=PlatformAiModerationPolicyResponse,
        tags=["platform-ai-moderation"],
    )
    async def get_platform_ai_moderation_policy(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformAiModerationPolicyResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_ai_moderation_policy_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform AI moderation policy is unavailable",
            )
        try:
            state = await platform_ai_moderation_policy_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform AI moderation policy is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformAiModerationPolicyResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            policy=AiModerationPolicyUpdateRequest.from_domain_policy(state.policy),
            is_default_policy=state.is_default_policy,
        )

    @app.put(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/channel-purposes",
        response_model=PlatformChannelPurposesResponse,
        tags=["platform-channel-purposes"],
    )
    async def update_platform_channel_purpose(
        organization_id: UUID,
        connection_id: UUID,
        payload: ChannelPurposeUpdateRequest,
        request: Request,
    ) -> PlatformChannelPurposesResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_channel_purpose_update_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform channel purposes are unavailable",
            )
        try:
            purposes = await platform_channel_purpose_update_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                purpose=payload.purpose,
                channel_id=payload.channel_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform channel purposes are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformChannelPurposesResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=purposes.platform,
            items=[
                ChannelPurposeAssignmentResponse(purpose=purpose, channel_id=channel_id)
                for purpose, channel_id in purposes.assignments.items()
            ],
        )

    @app.get(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/welcome-settings",
        response_model=PlatformWelcomeSettingsResponse,
        tags=["platform-welcome"],
    )
    async def get_platform_welcome_settings(
        organization_id: UUID, connection_id: UUID, request: Request
    ) -> PlatformWelcomeSettingsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_welcome_settings_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform welcome settings are unavailable",
            )
        try:
            settings = await platform_welcome_settings_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform welcome settings are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformWelcomeSettingsResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=settings.platform,
            title=settings.title,
            description=settings.description,
            thumbnail_url=settings.thumbnail_url,
            footer_text=settings.footer_text,
            footer_icon_url=settings.footer_icon_url,
            color=settings.color,
            is_enabled=settings.is_enabled,
            rules_channel_id=settings.rules_channel_id,
            roles_channel_id=settings.roles_channel_id,
        )

    @app.put(
        "/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/welcome-settings",
        response_model=PlatformWelcomeSettingsResponse,
        tags=["platform-welcome"],
    )
    async def update_platform_welcome_settings(
        organization_id: UUID,
        connection_id: UUID,
        payload: PlatformWelcomeSettingsUpdateRequest,
        request: Request,
    ) -> PlatformWelcomeSettingsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_welcome_settings_update_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform welcome settings are unavailable",
            )
        try:
            settings = await platform_welcome_settings_update_use_case.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=request.state.correlation_id,
                settings=PlatformWelcomeSettings(platform=Platform.DISCORD, **payload.model_dump()),
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Platform welcome settings are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformWelcomeSettingsResponse(
            organization_id=str(organization_id),
            connection_id=str(connection_id),
            platform=settings.platform,
            title=settings.title,
            description=settings.description,
            thumbnail_url=settings.thumbnail_url,
            footer_text=settings.footer_text,
            footer_icon_url=settings.footer_icon_url,
            color=settings.color,
            is_enabled=settings.is_enabled,
            rules_channel_id=settings.rules_channel_id,
            roles_channel_id=settings.roles_channel_id,
        )

    return app


app = create_app()
