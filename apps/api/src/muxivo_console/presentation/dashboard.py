"""HTTP boundary for resource-bound platform dashboard summaries."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from muxivo_console.application.get_platform_dashboard_summary import GetPlatformDashboardSummary
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.contracts.v1.dashboard import PlatformDashboardSummaryResponse


def create_dashboard_router(dashboard: GetPlatformDashboardSummary) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/organizations/{organization_id}/platform-connections",
        tags=["platform-dashboard"],
    )

    @router.get(
        "/{connection_id}/dashboard-summary",
        response_model=PlatformDashboardSummaryResponse,
    )
    async def get_dashboard_summary(
        organization_id: UUID,
        connection_id: UUID,
        request: Request,
    ) -> PlatformDashboardSummaryResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        try:
            summary = await dashboard.execute(
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
                detail="Dashboard summary is unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        return PlatformDashboardSummaryResponse(
            organization_id=organization_id,
            connection_id=connection_id,
            platform=summary.platform,
            messages_today=summary.messages_today,
            ai_flagged_today=summary.ai_flagged_today,
            creator_sources=summary.creator_sources,
            bot_latency_ms=summary.bot_latency_ms,
        )

    return router
