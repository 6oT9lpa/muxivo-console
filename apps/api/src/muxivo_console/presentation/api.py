from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import Response

from muxivo_console.application.list_control_modules import AccessDeniedError, ListControlModules
from muxivo_console.application.register_email_password import (
    RegisterEmailPassword,
    RegisterEmailPasswordCommand,
    RegistrationRejectedError,
)
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.contracts.v1.authentication import (
    EmailPasswordRegistrationRequest,
    EmailPasswordRegistrationResponse,
)
from muxivo_console.contracts.v1.control_modules import (
    ControlModuleListResponse,
    ControlModuleResponse,
)
from muxivo_console.infrastructure.development import (
    DenyByDefaultOrganizationAuthorizer,
    StaticModuleCatalog,
)

SESSION_COOKIE_NAME = "__Host-muxivo_session"


def create_app(
    control_modules_use_case: ListControlModules | None = None,
    registration_use_case: RegisterEmailPassword | None = None,
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

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

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
                actor_id=actor_id, organization_id=organization_id
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
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
