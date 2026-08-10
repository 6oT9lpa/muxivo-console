"""Discord-specific Server Stats Control API adapter."""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.server_stats import (
    PlatformServerStats,
    ServerChannelStats,
    ServerDailyStats,
    ServerHourlyStats,
    ServerStatsSummary,
)
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer


@dataclass(frozen=True, slots=True)
class DiscordServerStatsApi:
    base_url: str
    assertions: HmacControlAssertionIssuer
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        allowed_schemes = {"https"}
        if self.allow_insecure_http:
            allowed_schemes.add("http")
        if parsed.scheme not in allowed_schemes or not parsed.netloc or parsed.username:
            raise ValueError("Discord Control API base URL must be an absolute service URL.")

    async def get_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/server-stats",
                    params={"period": period_days},
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API server stats request failed."
            ) from error
        return _parse_discord_server_stats(payload, external_resource_id)


def _parse_discord_server_stats(payload: Any, expected_guild_id: str) -> PlatformServerStats:
    if (
        not isinstance(payload, dict)
        or payload.get("guild_id") != expected_guild_id
        or not isinstance(payload.get("stats"), dict)
    ):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid server stats payload."
        )
    stats = payload["stats"]
    try:
        summary_payload = _object(stats, "summary")
        summary = ServerStatsSummary(
            total_messages=_counter(summary_payload, "total_messages"),
            active_users=_counter(summary_payload, "active_users"),
            active_channels=_counter(summary_payload, "active_channels"),
            daily_active_users=_counter(summary_payload, "dau"),
            weekly_active_users=_counter(summary_payload, "wau"),
            monthly_active_users=_counter(summary_payload, "mau"),
            messages_per_active_user=_non_negative_number(
                summary_payload.get("messages_per_active_user", 0)
            ),
            voice_users=_counter(summary_payload, "voice_voice_users"),
            total_voice_minutes=_counter(summary_payload, "voice_total_voice_minutes"),
            joins=_counter(summary_payload, "joins"),
            leaves=_counter(summary_payload, "leaves"),
            joins_24h=_counter(summary_payload, "joins_24h"),
            joins_7d=_counter(summary_payload, "joins_7d"),
            joins_30d=_counter(summary_payload, "joins_30d"),
            leaves_24h=_counter(summary_payload, "leaves_24h"),
            leaves_7d=_counter(summary_payload, "leaves_7d"),
            leaves_30d=_counter(summary_payload, "leaves_30d"),
            net_member_growth=_integer(summary_payload.get("net_member_growth", 0)),
            current_member_count=_counter(summary_payload, "current_member_count"),
            moderation_events=_counter(summary_payload, "moderation_events"),
            membership_history_since=_optional_string(
                summary_payload.get("membership_history_since")
            ),
            membership_history_complete=_boolean(
                summary_payload.get("membership_history_complete", False)
            ),
            period_days=_period(summary_payload.get("period_days")),
        )
        channels = tuple(
            ServerChannelStats(
                channel_id=str(_required(item, "channel_id")),
                channel_name=_string(item, "channel_name"),
                messages=_counter(item, "messages"),
            )
            for item in _object_list(stats, "channels")
        )
        hourly = tuple(
            ServerHourlyStats(
                hour=_counter(item, "hour"),
                count=_counter(item, "count"),
            )
            for item in _object_list(stats, "hourly")
        )
        daily = tuple(
            ServerDailyStats(
                date=_string(item, "date"),
                count=_counter(item, "count"),
            )
            for item in _object_list(stats, "daily")
        )
        return PlatformServerStats(Platform.DISCORD, summary, channels, hourly, daily)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid server statistics."
        ) from error


def _object(container: dict[str, Any], key: str) -> dict[str, Any]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object.")
    return value


def _object_list(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = container.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be an object list.")
    return value


def _required(container: dict[str, Any], key: str) -> Any:
    if key not in container:
        raise KeyError(key)
    return container[key]


def _counter(container: dict[str, Any], key: str) -> int:
    value = container.get(key, 0)
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer.")
    return value


def _integer(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Value must be an integer.")
    return value


def _non_negative_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("Value must be a non-negative number.")
    return float(value)


def _string(container: dict[str, Any], key: str) -> str:
    value = _required(container, key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Optional string is invalid.")
    return value


def _boolean(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Value must be a boolean.")
    return value


def _period(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 365:
        raise ValueError("period_days must be between 1 and 365.")
    return value
