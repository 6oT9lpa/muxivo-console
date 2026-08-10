"""Production composition root; this is the only place concrete adapters meet."""

from muxivo_console.application.authenticate_email_password import AuthenticateEmailPassword
from muxivo_console.application.begin_identity_link import BeginIdentityLink
from muxivo_console.application.complete_identity_link import CompleteIdentityLink
from muxivo_console.application.create_browser_session import CreateBrowserSession
from muxivo_console.application.create_organization import CreateOrganization
from muxivo_console.application.get_platform_health import GetPlatformHealth
from muxivo_console.application.link_verified_identity import LinkVerifiedIdentity
from muxivo_console.application.list_control_modules import ListControlModules
from muxivo_console.application.list_organizations import ListOrganizations
from muxivo_console.application.list_platform_connections import ListPlatformConnections
from muxivo_console.application.organization_authorizer import MembershipOrganizationAuthorizer
from muxivo_console.application.register_email_password import RegisterEmailPassword
from muxivo_console.application.register_platform_connection import RegisterPlatformConnection
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.application.revoke_browser_session import RevokeBrowserSession
from muxivo_console.infrastructure.discord_control_api import (
    DiscordControlApiCatalog,
    DiscordPlatformConnectionVerifier,
    HmacControlAssertionIssuer,
)
from muxivo_console.infrastructure.discord_oauth import DiscordOAuthClient
from muxivo_console.infrastructure.naming import RandomSuffixOrganizationSlugGenerator
from muxivo_console.infrastructure.persistence.connection_repository import (
    SqlAlchemyPlatformConnectionReader,
    SqlAlchemyPlatformConnectionWriter,
)
from muxivo_console.infrastructure.persistence.database import create_session_factory
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
)
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationAccessReader,
    SqlAlchemyOrganizationCreationWriter,
    SqlAlchemyOrganizationMembershipReader,
    SqlAlchemyUserStatusReader,
)
from muxivo_console.infrastructure.persistence.registration_writer import (
    SqlAlchemyEmailPasswordRegistrationWriter,
)
from muxivo_console.infrastructure.persistence.session_repository import (
    SqlAlchemyAuthSessionReader,
    SqlAlchemyAuthSessionRevoker,
    SqlAlchemyAuthSessionWriter,
)
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
from muxivo_console.infrastructure.settings import ConsoleSettings
from muxivo_console.presentation.api import create_app
from muxivo_console.presentation.browser_sessions import create_browser_session_router
from muxivo_console.presentation.organizations import create_organization_query_router


def create_production_app(settings: ConsoleSettings):
    """Compose a fully wired API without leaking infrastructure into handlers."""
    sessions = create_session_factory(settings.database_url)
    identifiers = Uuid7IdentifierGenerator()
    clock = UtcClock()
    user_statuses = SqlAlchemyUserStatusReader(sessions)
    email_protector = FernetEmailProtector(
        lookup_key=settings.email_lookup_key,
        encryption_key=settings.email_encryption_key,
    )
    password_hasher = Argon2idPasswordHasher()
    session_hasher = HmacSessionTokenHasher(settings.session_token_pepper)
    session_creator = CreateBrowserSession(
        identifiers=identifiers,
        clock=clock,
        user_statuses=user_statuses,
        token_issuer=SecureOpaqueSessionTokenIssuer(),
        token_hasher=session_hasher,
        sessions=SqlAlchemyAuthSessionWriter(sessions),
    )
    registrations = RegisterEmailPassword(
        identifiers=identifiers,
        email_normalizer=ValidatedEmailAddressNormalizer(),
        email_protector=email_protector,
        password_hasher=password_hasher,
        registrations=SqlAlchemyEmailPasswordRegistrationWriter(sessions),
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
    organization_memberships = SqlAlchemyOrganizationMembershipReader(sessions)
    modules = ListControlModules(
        authorizer=MembershipOrganizationAuthorizer(organization_memberships),
        catalog=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
    )
    organizations = CreateOrganization(
        identifiers=identifiers,
        user_statuses=user_statuses,
        slugs=RandomSuffixOrganizationSlugGenerator(),
        organizations=SqlAlchemyOrganizationCreationWriter(sessions),
    )
    platform_connections = RegisterPlatformConnection(
        authorizer=MembershipOrganizationAuthorizer(organization_memberships),
        verifier=DiscordPlatformConnectionVerifier(
            settings.discord_control_base_url,
            assertions,
            SqlAlchemyLoginIdentityReader(sessions),
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
        identifiers=identifiers,
        connections=SqlAlchemyPlatformConnectionWriter(sessions),
    )
    listed_platform_connections = ListPlatformConnections(
        authorizer=MembershipOrganizationAuthorizer(organization_memberships),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
    )
    platform_health = GetPlatformHealth(
        authorizer=MembershipOrganizationAuthorizer(organization_memberships),
        connections=SqlAlchemyPlatformConnectionReader(sessions),
        health=DiscordControlApiCatalog(
            settings.discord_control_base_url,
            assertions,
            allow_insecure_http=settings.allow_insecure_discord_control_http,
        ),
    )
    discord_identity_link_start = None
    discord_identity_link_complete = None
    discord_authorization_url = None
    if settings.discord_oauth is not None:
        oauth_client = DiscordOAuthClient(
            client_id=settings.discord_oauth.client_id,
            client_secret=settings.discord_oauth.client_secret,
            redirect_uri=settings.discord_oauth.redirect_uri,
        )
        identity_linker = LinkVerifiedIdentity(
            identifiers=identifiers,
            user_statuses=user_statuses,
            identities=SqlAlchemyLoginIdentityLinkWriter(sessions),
        )
        opaque_secrets = FernetOpaqueValueProtector(settings.email_encryption_key)
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
            provider_client=oauth_client,
            linker=identity_linker,
        )
        discord_authorization_url = oauth_client.authorization_url
    app = create_app(
        control_modules_use_case=modules,
        registration_use_case=registrations,
        authentication_use_case=authentication,
        organization_creation_use_case=organizations,
        platform_connection_registration_use_case=platform_connections,
        platform_connections_use_case=listed_platform_connections,
        platform_health_use_case=platform_health,
        discord_identity_link_start=discord_identity_link_start,
        discord_identity_link_complete=discord_identity_link_complete,
        discord_authorization_url=discord_authorization_url,
        session_resolver=ResolveBrowserSession(
            clock=clock,
            token_hasher=session_hasher,
            sessions=SqlAlchemyAuthSessionReader(sessions),
            user_statuses=user_statuses,
        ),
    )
    app.include_router(
        create_browser_session_router(
            RevokeBrowserSession(
                identifiers=identifiers,
                clock=clock,
                sessions=SqlAlchemyAuthSessionRevoker(sessions),
            )
        )
    )
    app.include_router(
        create_organization_query_router(
            ListOrganizations(organizations=SqlAlchemyOrganizationAccessReader(sessions))
        )
    )
    return app
