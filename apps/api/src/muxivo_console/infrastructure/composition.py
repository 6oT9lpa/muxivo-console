"""Production composition root; this is the only place concrete adapters meet."""

from muxivo_console.application.accept_organization_invitation import AcceptOrganizationInvitation
from muxivo_console.application.authenticate_email_password import AuthenticateEmailPassword
from muxivo_console.application.begin_identity_link import BeginIdentityLink
from muxivo_console.application.begin_oauth_login import BeginOAuthLogin
from muxivo_console.application.change_email_password import ChangeEmailPassword
from muxivo_console.application.cleanup_security_records import CleanupSecurityRecords
from muxivo_console.application.complete_email_password_registration import (
    CompleteEmailPasswordRegistration,
)
from muxivo_console.application.complete_identity_link import CompleteIdentityLink
from muxivo_console.application.complete_oauth_login import CompleteOAuthLogin
from muxivo_console.application.complete_password_recovery import CompletePasswordRecovery
from muxivo_console.application.create_browser_session import CreateBrowserSession
from muxivo_console.application.create_organization import CreateOrganization
from muxivo_console.application.get_platform_ai_moderation_policy import (
    GetPlatformAiModerationPolicy,
)
from muxivo_console.application.get_platform_ai_moderation_summary import (
    GetPlatformAiModerationSummary,
)
from muxivo_console.application.get_platform_audit_timeline import GetPlatformAuditTimeline
from muxivo_console.application.get_platform_bot_settings import GetPlatformBotSettings
from muxivo_console.application.get_platform_channel_purposes import GetPlatformChannelPurposes
from muxivo_console.application.get_platform_dashboard_summary import GetPlatformDashboardSummary
from muxivo_console.application.get_platform_health import GetPlatformHealth
from muxivo_console.application.get_platform_integrations import GetPlatformIntegrations
from muxivo_console.application.get_platform_server_statistics import (
    GetPlatformServerStatistics,
)
from muxivo_console.application.get_platform_welcome_settings import (
    GetPlatformWelcomeSettings,
)
from muxivo_console.application.invite_organization_member import InviteOrganizationMember
from muxivo_console.application.link_verified_identity import LinkVerifiedIdentity
from muxivo_console.application.list_browser_sessions import ListBrowserSessions
from muxivo_console.application.list_control_modules import ListControlModules
from muxivo_console.application.list_organization_audit_events import (
    ListOrganizationAuditEvents,
)
from muxivo_console.application.list_organization_invitations import ListOrganizationInvitations
from muxivo_console.application.list_organizations import ListOrganizations
from muxivo_console.application.list_platform_connection_candidates import (
    ListPlatformConnectionCandidates,
)
from muxivo_console.application.list_platform_connection_channels import (
    ListPlatformConnectionChannels,
)
from muxivo_console.application.list_platform_connections import ListPlatformConnections
from muxivo_console.application.manage_login_identities import (
    ListLoginIdentities,
    UnlinkLoginIdentity,
)
from muxivo_console.application.manage_organization_members import (
    AddOrganizationMember,
    ListOrganizationMembers,
    RemoveOrganizationMember,
    UpdateOrganizationMember,
)
from muxivo_console.application.manage_platform_connection_lifecycle import (
    ManagePlatformConnectionLifecycle,
)
from muxivo_console.application.organization_authorizer import MembershipOrganizationAuthorizer
from muxivo_console.application.platform_connection_candidate_catalog_router import (
    PlatformConnectionCandidateCatalogRouter,
)
from muxivo_console.application.reauthenticate_browser_session import ReauthenticateBrowserSession
from muxivo_console.application.reconcile_platform_connections import ReconcilePlatformConnections
from muxivo_console.application.register_platform_connection import (
    PlatformConnectionVerifierRouter,
    RegisterPlatformConnection,
)
from muxivo_console.application.request_password_recovery import RequestPasswordRecovery
from muxivo_console.application.require_recent_authentication import RequireRecentAuthentication
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.application.revoke_all_browser_sessions import RevokeAllBrowserSessions
from muxivo_console.application.revoke_browser_session import RevokeBrowserSession
from muxivo_console.application.revoke_organization_invitation import (
    RevokeOrganizationInvitation,
)
from muxivo_console.application.start_email_password_registration import (
    StartEmailPasswordRegistration,
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
from muxivo_console.domain.activity import Platform
from muxivo_console.infrastructure.discord_connection_candidate_catalog import (
    DiscordPlatformConnectionCandidateCatalog,
)
from muxivo_console.infrastructure.discord_control_api import (
    DiscordControlApiCatalog,
    DiscordPlatformConnectionReconciliationProbe,
    DiscordPlatformConnectionVerifier,
    HmacControlAssertionIssuer,
)
from muxivo_console.infrastructure.discord_oauth import DiscordOAuthClient
from muxivo_console.infrastructure.in_memory_one_time_token_store import (
    InMemoryOneTimeTokenStore,
)
from muxivo_console.infrastructure.logging_redaction import install_secret_redaction_filter
from muxivo_console.infrastructure.metrics import InMemoryHttpMetricsRecorder
from muxivo_console.infrastructure.naming import RandomSuffixOrganizationSlugGenerator
from muxivo_console.infrastructure.notifications import (
    SmtpEmailPasswordRegistrationVerificationNotifier,
    SmtpOrganizationInvitationNotifier,
    SmtpPasswordRecoveryCompletionNotifier,
    SmtpPasswordRecoveryNotifier,
    UndeliveredEmailPasswordRegistrationVerificationNotifier,
    UndeliveredPasswordRecoveryCompletionNotifier,
)
from muxivo_console.infrastructure.openid_connect_oauth import OpenIdConnectOAuthClient
from muxivo_console.infrastructure.persistence.audit_repository import (
    SqlAlchemyAuditEventReader,
    SqlAlchemyAuditEventWriter,
)
from muxivo_console.infrastructure.persistence.connection_repository import (
    SqlAlchemyPlatformConnectionReader,
    SqlAlchemyPlatformConnectionWriter,
)
from muxivo_console.infrastructure.persistence.database import create_session_factory
from muxivo_console.infrastructure.persistence.database_readiness import (
    SqlAlchemyDatabaseReadinessProbe,
)
from muxivo_console.infrastructure.persistence.identity_link_transaction_writer import (
    SqlAlchemyIdentityLinkTransactionConsumer,
    SqlAlchemyIdentityLinkTransactionWriter,
)
from muxivo_console.infrastructure.persistence.identity_link_writer import (
    SqlAlchemyLoginIdentityLinkWriter,
)
from muxivo_console.infrastructure.persistence.identity_repository import (
    SqlAlchemyEmailPasswordAccountReader,
    SqlAlchemyLoginIdentityReader,
    SqlAlchemyPasswordCredentialRepository,
    SqlAlchemyUserEmailLookupReader,
)
from muxivo_console.infrastructure.persistence.identity_unlink_writer import (
    SqlAlchemyLoginIdentityUnlinkWriter,
)
from muxivo_console.infrastructure.persistence.oauth_login_transaction_repository import (
    SqlAlchemyOAuthLoginTransactionConsumer,
    SqlAlchemyOAuthLoginTransactionWriter,
)
from muxivo_console.infrastructure.persistence.organization_invitation_reader import (
    SqlAlchemyOrganizationInvitationReader,
)
from muxivo_console.infrastructure.persistence.organization_invitation_writer import (
    SqlAlchemyOrganizationInvitationWriter,
)
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationCreationWriter,
    SqlAlchemyOrganizationListingReader,
    SqlAlchemyOrganizationMemberRepository,
    SqlAlchemyOrganizationMembershipReader,
    SqlAlchemyUserStatusReader,
)
from muxivo_console.infrastructure.persistence.password_recovery_recipient_reader import (
    SqlAlchemyPasswordRecoveryRecipientReader,
)
from muxivo_console.infrastructure.persistence.password_recovery_repository import (
    SqlAlchemyPasswordRecoveryRepository,
)
from muxivo_console.infrastructure.persistence.registration_writer import (
    SqlAlchemyEmailPasswordRegistrationWriter,
)
from muxivo_console.infrastructure.persistence.security_cleanup_repository import (
    SqlAlchemySecurityRecordCleaner,
)
from muxivo_console.infrastructure.persistence.session_last_seen_repository import (
    SqlAlchemyAuthSessionLastSeenUpdater,
)
from muxivo_console.infrastructure.persistence.session_repository import (
    SqlAlchemyAuthSessionListingReader,
    SqlAlchemyAuthSessionReader,
    SqlAlchemyAuthSessionReauthenticationWriter,
    SqlAlchemyAuthSessionRevoker,
    SqlAlchemyAuthSessionWriter,
)
from muxivo_console.infrastructure.rate_limiting import (
    DEFAULT_AUTH_RATE_LIMIT_RULES,
    InMemoryFixedWindowRateLimiter,
    RedisFixedWindowCounter,
    RedisFixedWindowRateLimiter,
)
from muxivo_console.infrastructure.reconciliation_worker import (
    PeriodicPlatformConnectionReconciliationWorker,
    PeriodicReconciliationWorkerSettings,
)
from muxivo_console.infrastructure.redis_one_time_token_store import RedisOneTimeTokenStore
from muxivo_console.infrastructure.security import (
    Argon2idPasswordHasher,
    FernetEmailProtector,
    FernetOpaqueValueProtector,
    HmacSessionTokenHasher,
    SecureOpaqueSessionTokenIssuer,
    UtcClock,
    Uuid7IdentifierGenerator,
    ValidatedEmailAddressNormalizer,
)
from muxivo_console.infrastructure.security_cleanup_worker import (
    PeriodicSecurityCleanupWorker,
    PeriodicSecurityCleanupWorkerSettings,
)
from muxivo_console.infrastructure.session_fingerprint import HmacSessionFingerprintHasher
from muxivo_console.infrastructure.settings import ConsoleSettings
from muxivo_console.infrastructure.structured_logging import install_structured_logging
from muxivo_console.infrastructure.twitch_connection_candidate_catalog import (
    TwitchPlatformConnectionCandidateCatalog,
)
from muxivo_console.infrastructure.twitch_control_api import (
    TwitchPlatformConnectionReconciliationProbe,
    TwitchPlatformConnectionVerifier,
    TwitchPlatformHealthReader,
)
from muxivo_console.infrastructure.twitch_oauth import TwitchOAuthClient
from muxivo_console.infrastructure.undelivered_organization_invitation_notifier import (
    UndeliveredOrganizationInvitationNotifier,
)
from muxivo_console.infrastructure.undelivered_password_recovery_notifier import (
    UndeliveredPasswordRecoveryNotifier,
)
from muxivo_console.presentation.api import (
    BrowserSecurityPolicy,
    BrowserSessionCookieSettings,
    create_app,
)


def create_production_app(
    settings: ConsoleSettings,
    *,
    browser_session_cookies: BrowserSessionCookieSettings | None = None,
):
    """Compose a fully wired API without leaking infrastructure into handlers."""
    install_secret_redaction_filter()
    install_structured_logging()
    sessions = create_session_factory(settings.database_url)
    identifiers = Uuid7IdentifierGenerator()
    clock = UtcClock()
    user_statuses = SqlAlchemyUserStatusReader(sessions)
    membership_reader = SqlAlchemyOrganizationMembershipReader(sessions)
    organization_member_repository = SqlAlchemyOrganizationMemberRepository(sessions)
    organization_reader = SqlAlchemyOrganizationListingReader(sessions)
    email_protector = FernetEmailProtector(
        lookup_key=settings.email_lookup_key,
        encryption_key=settings.email_encryption_key,
    )
    password_hasher = Argon2idPasswordHasher()
    session_hasher = HmacSessionTokenHasher(settings.session_token_pepper)
    session_fingerprint_hasher = HmacSessionFingerprintHasher(settings.session_token_pepper)
    one_time_token_store = _one_time_token_store_for(settings)
    session_creator = CreateBrowserSession(
        identifiers=identifiers,
        clock=clock,
        user_statuses=user_statuses,
        token_issuer=SecureOpaqueSessionTokenIssuer(),
        token_hasher=session_hasher,
        fingerprint_hasher=session_fingerprint_hasher,
        sessions=SqlAlchemyAuthSessionWriter(sessions),
    )
    listed_sessions = ListBrowserSessions(
        clock=clock,
        user_statuses=user_statuses,
        sessions=SqlAlchemyAuthSessionListingReader(sessions),
    )
    session_bulk_revoker = RevokeAllBrowserSessions(
        identifiers=identifiers,
        clock=clock,
        sessions=SqlAlchemyAuthSessionRevoker(sessions),
        recent_authentication=RequireRecentAuthentication(clock=clock),
    )
    listed_login_identities = ListLoginIdentities(
        user_statuses=user_statuses,
        identities=SqlAlchemyLoginIdentityReader(sessions),
    )
    unlinked_login_identities = UnlinkLoginIdentity(
        identifiers=identifiers,
        user_statuses=user_statuses,
        identities=SqlAlchemyLoginIdentityReader(sessions),
        unlinker=SqlAlchemyLoginIdentityUnlinkWriter(sessions),
        recent_authentication=RequireRecentAuthentication(clock=clock),
    )
    password_credentials = SqlAlchemyPasswordCredentialRepository(sessions)
    password_change = ChangeEmailPassword(
        identifiers=identifiers,
        clock=clock,
        user_statuses=user_statuses,
        credentials=password_credentials,
        credential_writer=password_credentials,
        password_hasher=password_hasher,
        recent_authentication=RequireRecentAuthentication(clock=clock),
    )
    session_reauthentication = ReauthenticateBrowserSession(
        identifiers=identifiers,
        clock=clock,
        user_statuses=user_statuses,
        credentials=password_credentials,
        password_hasher=password_hasher,
        sessions=SqlAlchemyAuthSessionReauthenticationWriter(sessions),
    )
    password_recovery_repository = SqlAlchemyPasswordRecoveryRepository(sessions)
    password_recovery_notifier = (
        SmtpPasswordRecoveryNotifier(settings.password_recovery_smtp)
        if settings.password_recovery_smtp is not None
        else UndeliveredPasswordRecoveryNotifier()
    )
    password_recovery_completion_notifier = (
        SmtpPasswordRecoveryCompletionNotifier(settings.password_recovery_smtp)
        if settings.password_recovery_smtp is not None
        else UndeliveredPasswordRecoveryCompletionNotifier()
    )
    password_recovery_request = RequestPasswordRecovery(
        identifiers=identifiers,
        clock=clock,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_lookup_hasher=email_protector,
        token_issuer=SecureOpaqueSessionTokenIssuer(),
        token_hasher=session_hasher,
        accounts=SqlAlchemyEmailPasswordAccountReader(sessions),
        transactions=password_recovery_repository,
        recovery_tokens=one_time_token_store,
        notifier=password_recovery_notifier,
    )
    organization_invitation_notifier = (
        SmtpOrganizationInvitationNotifier(settings.password_recovery_smtp)
        if settings.password_recovery_smtp is not None
        else UndeliveredOrganizationInvitationNotifier()
    )
    organization_invitation_reader = SqlAlchemyOrganizationInvitationReader(sessions)
    organization_invitation_writer = SqlAlchemyOrganizationInvitationWriter(sessions)
    password_recovery_completion = CompletePasswordRecovery(
        identifiers=identifiers,
        clock=clock,
        token_hasher=session_hasher,
        password_hasher=password_hasher,
        completions=password_recovery_repository,
        recovery_tokens=one_time_token_store,
        recipients=SqlAlchemyPasswordRecoveryRecipientReader(sessions, email_protector),
        notifier=password_recovery_completion_notifier,
    )
    registration_completion = CompleteEmailPasswordRegistration(
        identifiers=identifiers,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_protector=email_protector,
        registrations=SqlAlchemyEmailPasswordRegistrationWriter(sessions),
    )
    if settings.password_recovery_smtp is not None:
        registration_verification_notifier = SmtpEmailPasswordRegistrationVerificationNotifier(
            settings.password_recovery_smtp
        )
    else:
        registration_verification_notifier = (
            UndeliveredEmailPasswordRegistrationVerificationNotifier()
        )
    registration_verification_start = StartEmailPasswordRegistration(
        identifiers=identifiers,
        clock=clock,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_protector=email_protector,
        password_hasher=password_hasher,
        token_issuer=SecureOpaqueSessionTokenIssuer(),
        token_hasher=session_hasher,
        accounts=SqlAlchemyEmailPasswordAccountReader(sessions),
        pending_registrations=one_time_token_store,
        notifier=registration_verification_notifier,
    )
    registration_verification_complete = VerifyEmailPasswordRegistration(
        token_hasher=session_hasher,
        email_protector=email_protector,
        pending_registrations=one_time_token_store,
        registrations=registration_completion,
    )
    authentication = AuthenticateEmailPassword(
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_lookup_hasher=email_protector,
        accounts=SqlAlchemyEmailPasswordAccountReader(sessions),
        password_hasher=password_hasher,
        session_creator=session_creator,
    )
    assertions = HmacControlAssertionIssuer(
        issuer="muxivo-console",
        audience="muxivo-discord-control",
        signing_key=settings.discord_control_signing_key,
        clock=clock,
    )
    discord_control_api = DiscordControlApiCatalog(
        settings.discord_control_base_url,
        assertions,
        allow_insecure_http=settings.allow_insecure_discord_control_http,
        identities=SqlAlchemyLoginIdentityReader(sessions),
    )
    modules = ListControlModules(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        catalog=discord_control_api,
    )
    organizations = CreateOrganization(
        identifiers=identifiers,
        user_statuses=user_statuses,
        slugs=RandomSuffixOrganizationSlugGenerator(),
        organizations=SqlAlchemyOrganizationCreationWriter(sessions),
    )
    listed_organizations = ListOrganizations(
        user_statuses=user_statuses,
        organizations=organization_reader,
    )
    listed_organization_members = ListOrganizationMembers(
        memberships=membership_reader,
        members=organization_member_repository,
    )
    organization_member_add = AddOrganizationMember(
        identifiers=identifiers,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_lookup_hasher=email_protector,
        invitees=SqlAlchemyUserEmailLookupReader(sessions),
        user_statuses=user_statuses,
        memberships=membership_reader,
        members=organization_member_repository,
    )
    organization_member_update = UpdateOrganizationMember(
        identifiers=identifiers,
        memberships=membership_reader,
        members=organization_member_repository,
    )
    organization_member_remove = RemoveOrganizationMember(
        identifiers=identifiers,
        memberships=membership_reader,
        members=organization_member_repository,
    )
    organization_invitation_create = InviteOrganizationMember(
        identifiers=identifiers,
        clock=clock,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_protector=email_protector,
        token_issuer=SecureOpaqueSessionTokenIssuer(),
        token_hasher=session_hasher,
        organizations=organization_reader,
        memberships=membership_reader,
        invitations=organization_invitation_writer,
        notifier=organization_invitation_notifier,
    )
    organization_invitation_list = ListOrganizationInvitations(
        memberships=membership_reader,
        invitations=organization_invitation_reader,
    )
    organization_invitation_revoke = RevokeOrganizationInvitation(
        clock=clock,
        identifiers=identifiers,
        memberships=membership_reader,
        invitations=organization_invitation_reader,
        writer=organization_invitation_writer,
    )
    organization_invitation_accept = AcceptOrganizationInvitation(
        clock=clock,
        identifiers=identifiers,
        token_hasher=session_hasher,
        user_emails=SqlAlchemyUserEmailLookupReader(sessions),
        user_statuses=user_statuses,
        memberships=membership_reader,
        invitations=organization_invitation_reader,
        writer=organization_invitation_writer,
    )
    platform_connection_verifiers = {
        Platform.DISCORD: DiscordPlatformConnectionVerifier(
            settings.discord_control_base_url,
            assertions,
            SqlAlchemyLoginIdentityReader(sessions),
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        )
    }
    twitch_control_assertions = None
    if settings.twitch_control is not None:
        twitch_control_assertions = HmacControlAssertionIssuer(
            issuer="muxivo-console",
            audience="muxivo-twitch-control",
            signing_key=settings.twitch_control.signing_key,
            clock=clock,
        )
        platform_connection_verifiers[Platform.TWITCH] = TwitchPlatformConnectionVerifier(
            settings.twitch_control.base_url,
            twitch_control_assertions,
            SqlAlchemyLoginIdentityReader(sessions),
            allow_insecure_http=settings.allow_insecure_twitch_control_http,
        )
    platform_connection_candidate_catalogs = {
        Platform.DISCORD: DiscordPlatformConnectionCandidateCatalog(
            settings.discord_control_base_url,
            assertions,
            SqlAlchemyLoginIdentityReader(sessions),
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        )
    }
    if settings.twitch_control is not None and twitch_control_assertions is not None:
        platform_connection_candidate_catalogs[Platform.TWITCH] = (
            TwitchPlatformConnectionCandidateCatalog(
                settings.twitch_control.base_url,
                twitch_control_assertions,
                SqlAlchemyLoginIdentityReader(sessions),
                allow_insecure_http=settings.allow_insecure_twitch_control_http,
            )
        )
    platform_connection_candidates = ListPlatformConnectionCandidates(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        candidates=PlatformConnectionCandidateCatalogRouter(platform_connection_candidate_catalogs),
    )
    platform_connections = RegisterPlatformConnection(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        verifier=PlatformConnectionVerifierRouter(platform_connection_verifiers),
        identifiers=identifiers,
        connections=SqlAlchemyPlatformConnectionWriter(sessions),
    )
    platform_connection_lifecycle = ManagePlatformConnectionLifecycle(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        lifecycle=SqlAlchemyPlatformConnectionWriter(sessions),
        identifiers=identifiers,
    )
    listed_platform_connections = ListPlatformConnections(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
    )
    audit_events = ListOrganizationAuditEvents(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        audit_events=SqlAlchemyAuditEventReader(sessions),
    )
    platform_health_readers = {Platform.DISCORD: discord_control_api}
    if settings.twitch_control is not None and twitch_control_assertions is not None:
        platform_health_readers[Platform.TWITCH] = TwitchPlatformHealthReader(
            settings.twitch_control.base_url,
            twitch_control_assertions,
            allow_insecure_http=settings.allow_insecure_twitch_control_http,
        )
    platform_health = GetPlatformHealth(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        health_readers=platform_health_readers,
    )
    platform_audit_timeline = GetPlatformAuditTimeline(
        MembershipOrganizationAuthorizer(membership_reader),
        SqlAlchemyPlatformConnectionReader(sessions),
        {Platform.DISCORD: discord_control_api},
    )
    platform_dashboard = GetPlatformDashboardSummary(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        dashboards={Platform.DISCORD: discord_control_api},
    )
    platform_channels = ListPlatformConnectionChannels(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        channel_catalogs={Platform.DISCORD: discord_control_api},
    )
    platform_channel_purposes = GetPlatformChannelPurposes(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        purposes=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
    )
    platform_ai_moderation_summary = GetPlatformAiModerationSummary(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        ai_moderation=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
    )
    platform_bot_settings = GetPlatformBotSettings(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        settings_readers={Platform.DISCORD: discord_control_api},
    )
    platform_integrations = GetPlatformIntegrations(
        MembershipOrganizationAuthorizer(membership_reader),
        SqlAlchemyPlatformConnectionReader(sessions),
        {Platform.DISCORD: discord_control_api},
    )
    platform_server_statistics = GetPlatformServerStatistics(
        MembershipOrganizationAuthorizer(membership_reader),
        SqlAlchemyPlatformConnectionReader(sessions),
        {Platform.DISCORD: discord_control_api},
    )
    platform_ai_moderation_policy = GetPlatformAiModerationPolicy(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        policies=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
            identities=SqlAlchemyLoginIdentityReader(sessions),
        ),
    )
    platform_channel_purpose_update = UpdatePlatformChannelPurpose(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        purposes=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
            identities=SqlAlchemyLoginIdentityReader(sessions),
        ),
    )
    platform_welcome_settings = GetPlatformWelcomeSettings(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        welcome_settings=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
    )
    platform_welcome_settings_update = UpdatePlatformWelcomeSettings(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        welcome_settings=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
            identities=SqlAlchemyLoginIdentityReader(sessions),
        ),
    )
    platform_ai_moderation_policy_update = UpdatePlatformAiModerationPolicy(
        authorizer=MembershipOrganizationAuthorizer(membership_reader),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        policies=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
            identities=SqlAlchemyLoginIdentityReader(sessions),
        ),
        recent_authentication=RequireRecentAuthentication(clock=clock),
        identifiers=identifiers,
        audit_events=SqlAlchemyAuditEventWriter(sessions),
    )
    background_services = []
    if settings.security_cleanup is not None:
        background_services.append(
            PeriodicSecurityCleanupWorker(
                cleanup=CleanupSecurityRecords(
                    clock=clock,
                    cleaner=SqlAlchemySecurityRecordCleaner(sessions),
                ),
                settings=PeriodicSecurityCleanupWorkerSettings(
                    interval_seconds=settings.security_cleanup.interval_seconds,
                    initial_delay_seconds=settings.security_cleanup.initial_delay_seconds,
                    session_retention_days=settings.security_cleanup.session_retention_days,
                    password_recovery_retention_hours=(
                        settings.security_cleanup.password_recovery_retention_hours
                    ),
                ),
            )
        )
    if settings.connection_reconciliation is not None:
        reconciliation_probe = DiscordPlatformConnectionReconciliationProbe(
            settings.discord_control_base_url,
            assertions,
            system_actor_id=settings.connection_reconciliation.system_actor_id,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        )
        reconciliation_probes = {Platform.DISCORD.value: reconciliation_probe}
        if settings.twitch_control is not None and twitch_control_assertions is not None:
            reconciliation_probes[Platform.TWITCH.value] = (
                TwitchPlatformConnectionReconciliationProbe(
                    settings.twitch_control.base_url,
                    twitch_control_assertions,
                    system_actor_id=settings.connection_reconciliation.system_actor_id,
                    allow_insecure_http=settings.allow_insecure_twitch_control_http,
                )
            )
        reconciler = ReconcilePlatformConnections(
            connections=SqlAlchemyPlatformConnectionReader(sessions),
            probes=reconciliation_probes,
            lifecycle=SqlAlchemyPlatformConnectionWriter(sessions),
            identifiers=identifiers,
        )
        background_services.append(
            PeriodicPlatformConnectionReconciliationWorker(
                reconciler=reconciler,
                identifiers=identifiers,
                settings=PeriodicReconciliationWorkerSettings(
                    system_actor_id=settings.connection_reconciliation.system_actor_id,
                    interval_seconds=settings.connection_reconciliation.interval_seconds,
                    initial_delay_seconds=settings.connection_reconciliation.initial_delay_seconds,
                    batch_limit=settings.connection_reconciliation.batch_limit,
                ),
            )
        )
    discord_identity_link_start = None
    discord_identity_link_complete = None
    twitch_identity_link_start = None
    twitch_identity_link_complete = None
    discord_login_start = None
    discord_login_complete = None
    twitch_login_start = None
    twitch_login_complete = None
    google_identity_link_start = None
    google_identity_link_complete = None
    google_login_start = None
    google_login_complete = None
    yandex_identity_link_start = None
    yandex_identity_link_complete = None
    yandex_login_start = None
    yandex_login_complete = None
    discord_authorization_url = None
    twitch_authorization_url = None
    google_authorization_url = None
    yandex_authorization_url = None
    identity_linker = None
    opaque_secrets = None
    if any(
        oauth is not None
        for oauth in (
            settings.discord_oauth,
            settings.twitch_oauth,
            settings.google_oauth,
            settings.yandex_oauth,
        )
    ):
        identity_linker = LinkVerifiedIdentity(
            identifiers=identifiers,
            user_statuses=user_statuses,
            identities=SqlAlchemyLoginIdentityLinkWriter(sessions),
        )
        opaque_secrets = FernetOpaqueValueProtector(settings.email_encryption_key)
    if settings.discord_oauth is not None:
        discord_oauth_client = DiscordOAuthClient(
            client_id=settings.discord_oauth.client_id,
            client_secret=settings.discord_oauth.client_secret,
            redirect_uri=settings.discord_oauth.redirect_uri,
        )
        discord_identity_link_start = BeginIdentityLink(
            identifiers=identifiers,
            clock=clock,
            user_statuses=user_statuses,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionWriter(sessions),
        )
        discord_identity_link_complete = CompleteIdentityLink(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionConsumer(sessions),
            provider_client=discord_oauth_client,
            linker=identity_linker,
        )
        discord_login_start = BeginOAuthLogin(
            identifiers=identifiers,
            clock=clock,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionWriter(sessions),
        )
        discord_login_complete = CompleteOAuthLogin(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionConsumer(sessions),
            provider_client=discord_oauth_client,
            identities=SqlAlchemyLoginIdentityReader(sessions),
            sessions=session_creator,
        )
        discord_authorization_url = discord_oauth_client.authorization_url
    if settings.twitch_oauth is not None:
        twitch_oauth_client = TwitchOAuthClient(
            client_id=settings.twitch_oauth.client_id,
            client_secret=settings.twitch_oauth.client_secret,
            redirect_uri=settings.twitch_oauth.redirect_uri,
        )
        twitch_identity_link_start = BeginIdentityLink(
            identifiers=identifiers,
            clock=clock,
            user_statuses=user_statuses,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionWriter(sessions),
        )
        twitch_identity_link_complete = CompleteIdentityLink(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionConsumer(sessions),
            provider_client=twitch_oauth_client,
            linker=identity_linker,
        )
        twitch_login_start = BeginOAuthLogin(
            identifiers=identifiers,
            clock=clock,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionWriter(sessions),
        )
        twitch_login_complete = CompleteOAuthLogin(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionConsumer(sessions),
            provider_client=twitch_oauth_client,
            identities=SqlAlchemyLoginIdentityReader(sessions),
            sessions=session_creator,
        )
        twitch_authorization_url = twitch_oauth_client.authorization_url
    if settings.google_oauth is not None:
        google_oauth_client = OpenIdConnectOAuthClient(
            provider_label="Google",
            client_id=settings.google_oauth.client_id,
            client_secret=settings.google_oauth.client_secret,
            redirect_uri=settings.google_oauth.redirect_uri,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scopes=("openid", "email", "profile"),
        )
        google_identity_link_start = BeginIdentityLink(
            identifiers=identifiers,
            clock=clock,
            user_statuses=user_statuses,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionWriter(sessions),
        )
        google_identity_link_complete = CompleteIdentityLink(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionConsumer(sessions),
            provider_client=google_oauth_client,
            linker=identity_linker,
        )
        google_login_start = BeginOAuthLogin(
            identifiers=identifiers,
            clock=clock,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionWriter(sessions),
        )
        google_login_complete = CompleteOAuthLogin(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionConsumer(sessions),
            provider_client=google_oauth_client,
            identities=SqlAlchemyLoginIdentityReader(sessions),
            sessions=session_creator,
        )
        google_authorization_url = google_oauth_client.authorization_url
    if settings.yandex_oauth is not None:
        yandex_oauth_client = OpenIdConnectOAuthClient(
            provider_label="Yandex ID",
            client_id=settings.yandex_oauth.client_id,
            client_secret=settings.yandex_oauth.client_secret,
            redirect_uri=settings.yandex_oauth.redirect_uri,
            authorize_url="https://oauth.yandex.com/authorize",
            token_url="https://oauth.yandex.com/token",
            userinfo_url="https://login.yandex.ru/info?format=json",
            scopes=("login:email", "login:info"),
            subject_field="id",
        )
        yandex_identity_link_start = BeginIdentityLink(
            identifiers=identifiers,
            clock=clock,
            user_statuses=user_statuses,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionWriter(sessions),
        )
        yandex_identity_link_complete = CompleteIdentityLink(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyIdentityLinkTransactionConsumer(sessions),
            provider_client=yandex_oauth_client,
            linker=identity_linker,
        )
        yandex_login_start = BeginOAuthLogin(
            identifiers=identifiers,
            clock=clock,
            token_issuer=SecureOpaqueSessionTokenIssuer(),
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionWriter(sessions),
        )
        yandex_login_complete = CompleteOAuthLogin(
            clock=clock,
            token_hasher=session_hasher,
            secrets=opaque_secrets,
            transactions=SqlAlchemyOAuthLoginTransactionConsumer(sessions),
            provider_client=yandex_oauth_client,
            identities=SqlAlchemyLoginIdentityReader(sessions),
            sessions=session_creator,
        )
        yandex_authorization_url = yandex_oauth_client.authorization_url
    return create_app(
        control_modules_use_case=modules,
        registration_verification_start_use_case=registration_verification_start,
        registration_verification_use_case=registration_verification_complete,
        authentication_use_case=authentication,
        organization_creation_use_case=organizations,
        organization_list_use_case=listed_organizations,
        organization_members_use_case=listed_organization_members,
        organization_member_add_use_case=organization_member_add,
        organization_member_update_use_case=organization_member_update,
        organization_member_remove_use_case=organization_member_remove,
        organization_invitation_create_use_case=organization_invitation_create,
        organization_invitation_list_use_case=organization_invitation_list,
        organization_invitation_revoke_use_case=organization_invitation_revoke,
        organization_invitation_accept_use_case=organization_invitation_accept,
        platform_connection_registration_use_case=platform_connections,
        platform_connection_candidates_use_case=platform_connection_candidates,
        platform_connection_lifecycle_use_case=platform_connection_lifecycle,
        platform_connections_use_case=listed_platform_connections,
        audit_events_use_case=audit_events,
        platform_health_use_case=platform_health,
        platform_audit_timeline_use_case=platform_audit_timeline,
        platform_dashboard_use_case=platform_dashboard,
        platform_channels_use_case=platform_channels,
        platform_channel_purposes_use_case=platform_channel_purposes,
        platform_ai_moderation_summary_use_case=platform_ai_moderation_summary,
        platform_bot_settings_use_case=platform_bot_settings,
        platform_integrations_use_case=platform_integrations,
        platform_server_statistics_use_case=platform_server_statistics,
        platform_ai_moderation_policy_use_case=platform_ai_moderation_policy,
        platform_ai_moderation_policy_update_use_case=platform_ai_moderation_policy_update,
        platform_channel_purpose_update_use_case=platform_channel_purpose_update,
        platform_welcome_settings_use_case=platform_welcome_settings,
        platform_welcome_settings_update_use_case=platform_welcome_settings_update,
        discord_identity_link_start=discord_identity_link_start,
        discord_identity_link_complete=discord_identity_link_complete,
        twitch_identity_link_start=twitch_identity_link_start,
        twitch_identity_link_complete=twitch_identity_link_complete,
        discord_login_start=discord_login_start,
        discord_login_complete=discord_login_complete,
        twitch_login_start=twitch_login_start,
        twitch_login_complete=twitch_login_complete,
        google_identity_link_start=google_identity_link_start,
        google_identity_link_complete=google_identity_link_complete,
        google_login_start=google_login_start,
        google_login_complete=google_login_complete,
        yandex_identity_link_start=yandex_identity_link_start,
        yandex_identity_link_complete=yandex_identity_link_complete,
        yandex_login_start=yandex_login_start,
        yandex_login_complete=yandex_login_complete,
        discord_authorization_url=discord_authorization_url,
        twitch_authorization_url=twitch_authorization_url,
        google_authorization_url=google_authorization_url,
        yandex_authorization_url=yandex_authorization_url,
        session_resolver=ResolveBrowserSession(
            clock=clock,
            token_hasher=session_hasher,
            sessions=SqlAlchemyAuthSessionReader(sessions),
            user_statuses=user_statuses,
            last_seen_updater=SqlAlchemyAuthSessionLastSeenUpdater(sessions),
        ),
        session_revoker=RevokeBrowserSession(
            identifiers=identifiers,
            clock=clock,
            sessions=SqlAlchemyAuthSessionRevoker(sessions),
        ),
        session_list_use_case=listed_sessions,
        session_bulk_revoker=session_bulk_revoker,
        session_reauthentication_use_case=session_reauthentication,
        login_identity_list_use_case=listed_login_identities,
        login_identity_unlink_use_case=unlinked_login_identities,
        password_change_use_case=password_change,
        password_recovery_request_use_case=password_recovery_request,
        password_recovery_completion_use_case=password_recovery_completion,
        rate_limiter=_rate_limiter_for(settings),
        metrics_recorder=InMemoryHttpMetricsRecorder(),
        readiness_probe=SqlAlchemyDatabaseReadinessProbe(sessions),
        browser_session_cookies=browser_session_cookies,
        session_fingerprint_hasher=session_fingerprint_hasher,
        browser_security_policy=BrowserSecurityPolicy(
            cors_allowed_origins=settings.cors_allowed_origins,
            hsts_enabled=settings.environment != "development",
        ),
        background_services=tuple(background_services),
    )


def create_development_app(settings: ConsoleSettings):
    """Compose the real application with a localhost-only browser cookie policy."""
    if settings.environment != "development":
        raise ValueError("The development ASGI entrypoint requires development settings.")
    return create_production_app(
        settings,
        browser_session_cookies=BrowserSessionCookieSettings.development(),
    )


def _one_time_token_store_for(settings: ConsoleSettings):
    """Use shared Redis for every short-lived authentication flow outside dev."""
    if settings.rate_limit is not None and settings.rate_limit.redis_url is not None:
        return RedisOneTimeTokenStore(settings.rate_limit.redis_url)
    if settings.environment == "development":
        return InMemoryOneTimeTokenStore()
    raise ValueError("Production one-time authentication flows require a Redis URL.")


def _rate_limiter_for(settings: ConsoleSettings):
    if settings.rate_limit is None or settings.rate_limit.backend == "memory":
        return InMemoryFixedWindowRateLimiter(DEFAULT_AUTH_RATE_LIMIT_RULES)
    if settings.rate_limit.redis_url is None:
        raise ValueError("Redis rate-limit backend requires a Redis URL.")
    return RedisFixedWindowRateLimiter(
        rules=DEFAULT_AUTH_RATE_LIMIT_RULES,
        counter=RedisFixedWindowCounter(settings.rate_limit.redis_url),
    )
