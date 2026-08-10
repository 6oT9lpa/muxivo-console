import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer
from muxivo_console.infrastructure.discord_server_stats_api import DiscordServerStatsApi


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 10, 18, 0, tzinfo=UTC)


def issuer() -> HmacControlAssertionIssuer:
    return HmacControlAssertionIssuer(
        issuer="muxivo-console",
        audience="muxivo-discord-control",
        signing_key=b"s" * 32,
        clock=FixedClock(),
    )


def decode_claims(token: str) -> dict[str, object]:
    encoded = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


def payload(guild_id: str) -> dict[str, object]:
    return {
        "guild_id": guild_id,
        "stats": {
            "summary": {
                "total_messages": 120,
                "active_users": 20,
                "active_channels": 4,
                "dau": 8,
                "wau": 15,
                "mau": 20,
                "messages_per_active_user": 6.0,
                "voice_voice_users": 5,
                "voice_total_voice_minutes": 300,
                "joins": 12,
                "leaves": 2,
                "joins_24h": 1,
                "joins_7d": 4,
                "joins_30d": 12,
                "leaves_24h": 0,
                "leaves_7d": 1,
                "leaves_30d": 2,
                "net_member_growth": 10,
                "current_member_count": 450,
                "moderation_events": 7,
                "membership_history_since": "2026-07-01T00:00:00+00:00",
                "membership_history_complete": False,
                "period_days": 30,
            },
            "channels": [
                {"channel_id": 123, "channel_name": "general", "messages": 80}
            ],
            "hourly": [{"hour": 12, "count": 11}],
            "daily": [{"date": "2026-08-10", "count": 22}],
        },
    }


@pytest.mark.asyncio
async def test_discord_stats_request_is_bound_to_connection_resource_and_period() -> None:
    organization_id, actor_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/{guild_id}/server-stats")
        assert request.url.params["period"] == "30"
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_resource_id"] == guild_id
        assert claims["resource"] == "console.control_modules"
        assert claims["action"] == "read"
        return httpx.Response(200, json=payload(guild_id))

    api = DiscordServerStatsApi(
        "http://discord-control.test",
        issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    stats = await api.get_for_connection(
        organization_id=organization_id,
        actor_id=actor_id,
        external_resource_id=guild_id,
        period_days=30,
        correlation_id=correlation_id,
    )

    assert stats.platform is Platform.DISCORD
    assert stats.summary.total_messages == 120
    assert stats.summary.voice_users == 5
    assert stats.channels[0].channel_name == "general"


@pytest.mark.asyncio
async def test_discord_stats_rejects_response_for_another_guild() -> None:
    api = DiscordServerStatsApi(
        "http://discord-control.test",
        issuer(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=payload("999999999999999999"))
        ),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="invalid server stats payload"):
        await api.get_for_connection(
            organization_id=uuid4(),
            actor_id=uuid4(),
            external_resource_id="123456789012345678",
            period_days=30,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_discord_stats_rejects_malformed_metric_types() -> None:
    guild_id = "123456789012345678"
    malformed = payload(guild_id)
    malformed["stats"]["summary"]["total_messages"] = True
    api = DiscordServerStatsApi(
        "http://discord-control.test",
        issuer(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=malformed)),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="invalid server statistics"):
        await api.get_for_connection(
            organization_id=uuid4(),
            actor_id=uuid4(),
            external_resource_id=guild_id,
            period_days=30,
            correlation_id=uuid4(),
        )
