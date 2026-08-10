"""Authenticated browser contract for configured platform adapter capabilities."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from muxivo_console.application.list_platform_adapters import ListPlatformAdapters
from muxivo_console.contracts.v1.platform_adapters import (
    PlatformAdapterListResponse,
    PlatformAdapterResponse,
)


def create_platform_adapter_router(adapters: ListPlatformAdapters) -> APIRouter:
    router = APIRouter(prefix="/api/v1/platform-adapters", tags=["platform-adapters"])

    @router.get("", response_model=PlatformAdapterListResponse)
    async def list_platform_adapters(request: Request) -> PlatformAdapterListResponse:
        if not isinstance(getattr(request.state, "actor_id", None), UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return PlatformAdapterListResponse(
            items=[
                PlatformAdapterResponse(
                    platform=descriptor.platform,
                    capabilities=sorted(
                        descriptor.capabilities,
                        key=lambda capability: capability.value,
                    ),
                )
                for descriptor in adapters.execute()
            ]
        )

    return router
