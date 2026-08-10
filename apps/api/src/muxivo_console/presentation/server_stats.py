"""HTTP boundary for resource-bound platform server statistics."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.get_platform_server_stats import GetPlatformServerStats
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.contracts.v1.server_stats import (
    PlatformServerStatsResponse,
    ServerChannelStatsResponse,
    ServerDailyStatsResponse,
    ServerHourlyStatsResponse,
    ServerStatsSummaryResponse,
)


def create_server_stats_router(server_stats: GetPlatformServerStats) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/organizations/{organization_id}/platform-connections",
        tags=["platform-server-stats"],
    )

    @router.get("/{connection_id}/server-stats", response_model=PlatformServerStatsResponse)
    async def get_server_stats(
        organization_id: UUID,
        connection_id: UUID,
        request: Request,
        period: int = Query(default=30, ge=1, le=365),
    ) -> PlatformServerStatsResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        try:
            stats = await server_stats.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                connection_id=connection_id,
                period_days=period,
                correlation_id=request.state.correlation_id,
            )
        except AccessDeniedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from error
        except PlatformHealthUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server stats are unavailable",
            ) from error
        except PlatformControlUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform control service is unavailable",
            ) from error
        summary = stats.summary
        return PlatformServerStatsResponse(
            organization_id=organization_id,
            connection_id=connection_id,
            platform=stats.platform,
            summary=ServerStatsSummaryResponse(
                total_messages=summary.total_messages,
                active_users=summary.active_users,
                active_channels=summary.active_channels,
                daily_active_users=summary.daily_active_users,
                weekly_active_users=summary.weekly_active_users,
                monthly_active_users=summary.monthly_active_users,
                messages_per_active_user=summary.messages_per_active_user,
                voice_users=summary.voice_users,
                total_voice_minutes=summary.total_voice_minutes,
                joins=summary.joins,
                leaves=summary.leaves,
                joins_24h=summary.joins_24h,
                joins_7d=summary.joins_7d,
                joins_30d=summary.joins_30d,
                leaves_24h=summary.leaves_24h,
                leaves_7d=summary.leaves_7d,
                leaves_30d=summary.leaves_30d,
                net_member_growth=summary.net_member_growth,
                current_member_count=summary.current_member_count,
                moderation_events=summary.moderation_events,
                membership_history_since=summary.membership_history_since,
                membership_history_complete=summary.membership_history_complete,
                period_days=summary.period_days,
            ),
            channels=[
                ServerChannelStatsResponse(
                    channel_id=item.channel_id,
                    channel_name=item.channel_name,
                    messages=item.messages,
                )
                for item in stats.channels
            ],
            hourly=[
                ServerHourlyStatsResponse(hour=item.hour, count=item.count)
                for item in stats.hourly
            ],
            daily=[
                ServerDailyStatsResponse(date=item.date, count=item.count)
                for item in stats.daily
            ],
        )

    return router
