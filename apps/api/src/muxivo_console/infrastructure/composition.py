"""Production composition root; this is the only place concrete adapters meet."""

from muxivo_console.application.authenticate_email_password import AuthenticateEmailPassword
from muxivo_console.application.create_browser_session import CreateBrowserSession
from muxivo_console.application.create_organization import CreateOrganization
from muxivo_console.application.list_control_modules import ListControlModules
from muxivo_console.application.organization_authorizer import MembershipOrganizationAuthorizer
from muxivo_console.application.register_email_password import RegisterEmailPassword
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.infrastructure.discord_control_api import (
    DiscordControlApiCatalog,
    HmacControlAssertionIssuer,
)
from muxivo_console.infrastructure.naming import RandomSuffixOrganizationSlugGenerator
from muxivo_console.infrastructure.persistence.database import create_session_factory
from muxivo_console.infrastructure.persistence.identity_repository import (
    SqlAlchemyEmailPasswordAccountReader,
)
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationCreationWriter,
    SqlAlchemyOrganizationMembershipReader,
    SqlAlchemyUserStatusReader,
)
from muxivo_console.infrastructure.persistence.registration_writer import (
    SqlAlchemyEmailPasswordRegistrationWriter,
)
from muxivo_console.infrastructure.persistence.session_repository import (
    SqlAlchemyAuthSessionReader,
    SqlAlchemyAuthSessionWriter,
)
from muxivo_console.infrastructure.security import (
    Argon2idPasswordHasher,
    FernetEmailProtector,
    HmacSessionTokenHasher,
    SecureOpaqueSessionTokenIssuer,
    UtcClock,
    Uuid7IdentifierGenerator,
    ValidatedEmailAddressNormalizer,
)
from muxivo_console.infrastructure.settings import ConsoleSettings
from muxivo_console.presentation.api import create_app


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
    modules = ListControlModules(
        authorizer=MembershipOrganizationAuthorizer(
            SqlAlchemyOrganizationMembershipReader(sessions)
        ),
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
    return create_app(
        control_modules_use_case=modules,
        registration_use_case=registrations,
        authentication_use_case=authentication,
        organization_creation_use_case=organizations,
        session_resolver=ResolveBrowserSession(
            clock=clock,
            token_hasher=session_hasher,
            sessions=SqlAlchemyAuthSessionReader(sessions),
            user_statuses=user_statuses,
        ),
    )
