from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status

from muxivo_console.application.list_control_modules import AccessDeniedError, ListControlModules
from muxivo_console.contracts.v1.control_modules import (
    ControlModuleListResponse,
    ControlModuleResponse,
)
from muxivo_console.infrastructure.development import (
    DenyByDefaultOrganizationAuthorizer,
    StaticModuleCatalog,
)


def create_app(use_case: ListControlModules | None = None) -> FastAPI:
    """Create the Console BFF without coupling application code to FastAPI."""
    control_modules = use_case or ListControlModules(
        authorizer=DenyByDefaultOrganizationAuthorizer(),
        catalog=StaticModuleCatalog(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="Muxivo Console API", version="1.0.0", lifespan=lifespan)

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

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
