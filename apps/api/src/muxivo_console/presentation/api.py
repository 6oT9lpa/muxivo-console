from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from hmac import compare_digest
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

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
from muxivo_console.application.complete_identity_link import (
    CompleteIdentityLink,
    CompleteIdentityLinkCommand,
    IdentityLinkCompletionRejectedError,
)
from muxivo_console.application.create_organization import (
    CreateOrganization,
    CreateOrganizationCommand,
    OrganizationCreationRejectedError,
)
from muxivo_console.application.get_platform_ai_moderation_summary import (
    GetPlatformAiModerationSummary,
)
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
from muxivo_console.application.get_platform_welcome_settings import (
    GetPlatformWelcomeSettings,
)
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    ListControlModules,
    PlatformControlUnavailableError,
)
from muxivo_console.application.list_platform_connection_channels import (
    ListPlatformConnectionChannels,
)
from muxivo_console.application.list_platform_connections import ListPlatformConnections
from muxivo_console.application.register_email_password import (
    RegisterEmailPassword,
    RegisterEmailPasswordCommand,
    RegistrationRejectedError,
)
from muxivo_console.application.register_platform_connection import (
    PlatformConnectionRegistrationRejectedError,
    RegisterPlatformConnection,
    RegisterPlatformConnectionCommand,
)
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.application.update_platform_channel_purpose import (
    UpdatePlatformChannelPurpose,
)
from muxivo_console.application.update_platform_welcome_settings import (
    UpdatePlatformWelcomeSettings,
)
from muxivo_console.contracts.v1.authentication import (
    EmailPasswordLoginRequest,
    EmailPasswordRegistrationRequest,
    EmailPasswordRegistrationResponse,
)
from muxivo_console.contracts.v1.control_modules import (
    ControlModuleListResponse,
    ControlModuleResponse,
)
from muxivo_console.contracts.v1.organizations import (
    OrganizationCreateRequest,
    OrganizationResponse,
)
from muxivo_console.contracts.v1.platform_ai_moderation import (
    PlatformAiModerationSummaryResponse,
)
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
    PlatformConnectionCreateRequest,
    PlatformConnectionListResponse,
    PlatformConnectionResponse,
)
from muxivo_console.contracts.v1.platform_dashboard import PlatformDashboardSummaryResponse
from muxivo_console.contracts.v1.platform_health import (
    HealthSignalResponse,
    PlatformHealthResponse,
)
from muxivo_console.contracts.v1.platform_welcome import (
    PlatformWelcomeSettingsResponse,
    PlatformWelcomeSettingsUpdateRequest,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.welcome import PlatformWelcomeSettings
from muxivo_console.infrastructure.development import (
    DenyByDefaultOrganizationAuthorizer,
    StaticModuleCatalog,
)

SESSION_COOKIE_NAME = "__Host-muxivo_session"
CSRF_COOKIE_NAME = "__Host-muxivo_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/email-password/registrations",
        "/api/v1/auth/email-password/sessions",
    }
)
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def create_app(
    control_modules_use_case: ListControlModules | None = None,
    registration_use_case: RegisterEmailPassword | None = None,
    authentication_use_case: AuthenticateEmailPassword | None = None,
    organization_creation_use_case: CreateOrganization | None = None,
    platform_connection_registration_use_case: RegisterPlatformConnection | None = None,
    platform_connections_use_case: ListPlatformConnections | None = None,
    platform_health_use_case: GetPlatformHealth | None = None,
    platform_dashboard_use_case: GetPlatformDashboardSummary | None = None,
    platform_channels_use_case: ListPlatformConnectionChannels | None = None,
    platform_channel_purposes_use_case: GetPlatformChannelPurposes | None = None,
    platform_ai_moderation_summary_use_case: GetPlatformAiModerationSummary | None = None,
    platform_channel_purpose_update_use_case: UpdatePlatformChannelPurpose | None = None,
    platform_welcome_settings_use_case: GetPlatformWelcomeSettings | None = None,
    platform_welcome_settings_update_use_case: UpdatePlatformWelcomeSettings | None = None,
    discord_identity_link_start: BeginIdentityLink | None = None,
    discord_identity_link_complete: CompleteIdentityLink | None = None,
    discord_authorization_url: Callable[..., str] | None = None,
    session_resolver: ResolveBrowserSession | None = None,
) -> FastAPI:
    """Create the Console BFF without coupling application code to FastAPI."""
    control_modules = control_modules_use_case or ListControlModules(
        authorizer=DenyByDefaultOrganizationAuthorizer(),
        catalog=StaticModuleCatalog(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="Muxivo Console API", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def attach_correlation_id(request: Request, call_next) -> Response:
        correlation_id = uuid4()
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        return response

    @app.middleware("http")
    async def resolve_browser_session(request: Request, call_next) -> Response:
        if session_resolver is not None:
            raw_token = request.cookies.get(SESSION_COOKIE_NAME)
            if raw_token is not None:
                try:
                    principal = await session_resolver.execute(raw_token)
                except Exception:
                    principal = None
                if principal is not None:
                    request.state.actor_id = principal.user_id
                    request.state.session_id = principal.session_id
                    request.state.assurance_level = principal.assurance_level
        return await call_next(request)

    @app.middleware("http")
    async def protect_mutations_from_csrf(request: Request, call_next) -> Response:
        """Require a browser-readable token to accompany every authenticated mutation."""
        if request.method not in SAFE_HTTP_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_cookie or not csrf_header or not compare_digest(csrf_cookie, csrf_header):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF validation failed"},
                )
        return await call_next(request)

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/identity-links/discord/authorizations",
        tags=["identity-links"],
    )
    async def begin_discord_identity_link(request: Request) -> dict[str, str | int]:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if discord_identity_link_start is None or discord_authorization_url is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Discord identity linking is unavailable",
            )
        try:
            started = await discord_identity_link_start.execute(
                BeginIdentityLinkCommand(
                    actor_id=actor_id,
                    provider=LoginIdentityProvider.DISCORD,
                    correlation_id=request.state.correlation_id,
                )
            )
            return {
                "authorization_url": discord_authorization_url(
                    state=started.state, code_challenge=started.code_challenge
                ),
                "expires_in_seconds": started.expires_in_seconds,
            }
        except IdentityLinkStartRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Discord identity linking failed"
            ) from error

    @app.get(
        "/api/v1/identity-links/discord/callback",
        tags=["identity-links"],
    )
    async def complete_discord_identity_link(
        code: str, state: str, request: Request
    ) -> dict[str, bool]:
        if discord_identity_link_complete is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Discord identity linking is unavailable",
            )
        try:
            await discord_identity_link_complete.execute(
                CompleteIdentityLinkCommand(
                    provider=LoginIdentityProvider.DISCORD,
                    state=state,
                    authorization_code=code,
                    correlation_id=request.state.correlation_id,
                )
            )
        except IdentityLinkCompletionRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discord identity linking failed",
            ) from error
        return {"linked": True}

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

    @app.post(
        "/api/v1/organizations/{organization_id}/platform-connections",
        response_model=PlatformConnectionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["platform-connections"],
    )
    async def register_platform_connection(
        organization_id: UUID, payload: PlatformConnectionCreateRequest, request: Request
    ) -> PlatformConnectionResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if platform_connection_registration_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform connection registration is unavailable",
            )
        try:
            connection = await platform_connection_registration_use_case.execute(
                RegisterPlatformConnectionCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    platform=payload.platform,
                    external_resource_id=payload.external_resource_id,
                    correlation_id=request.state.correlation_id,
                )
            )
        except PlatformConnectionRegistrationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform connection registration failed",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformConnectionResponse.model_validate(connection, from_attributes=True)

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
            items=[
                PlatformConnectionResponse.model_validate(connection, from_attributes=True)
                for connection in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @app.post(
        "/api/v1/auth/email-password/registrations",
        response_model=EmailPasswordRegistrationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["authentication"],
    )
    async def register_email_password(
        payload: EmailPasswordRegistrationRequest, request: Request
    ) -> EmailPasswordRegistrationResponse:
        if registration_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registration is unavailable",
            )
        try:
            await registration_use_case.execute(
                RegisterEmailPasswordCommand(
                    email=str(payload.email),
                    password=payload.password.get_secret_value(),
                    display_name=payload.display_name,
                    correlation_id=request.state.correlation_id,
                )
            )
        except RegistrationRejectedError:
            pass
        return EmailPasswordRegistrationResponse()

    @app.post(
        "/api/v1/auth/email-password/sessions",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )
    async def authenticate_email_password(
        payload: EmailPasswordLoginRequest, request: Request
    ) -> Response:
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
                )
            )
        except AuthenticationRejectedError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            ) from error

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=issued_session.raw_token,
            expires=issued_session.expires_at,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=issued_session.raw_csrf_token,
            expires=issued_session.expires_at,
            path="/",
            secure=True,
            httponly=False,
            samesite="lax",
        )
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
