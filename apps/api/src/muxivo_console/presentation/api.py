from collections.abc import AsyncIterator
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
from muxivo_console.application.create_organization import (
    CreateOrganization,
    CreateOrganizationCommand,
    OrganizationCreationRejectedError,
)
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    ListControlModules,
    PlatformControlUnavailableError,
)
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
from muxivo_console.contracts.v1.platform_connections import (
    PlatformConnectionCreateRequest,
    PlatformConnectionResponse,
)
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

    return app


app = create_app()
