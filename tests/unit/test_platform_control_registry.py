from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.infrastructure.platform_control_registry import PlatformControlRegistry


class Adapter:
    def __init__(self, platform: Platform) -> None:
        self.platform = platform
        self.calls: list[tuple[str, dict]] = []

    async def list_modules(self, **kwargs):
        self.calls.append(("modules", kwargs))
        return (
            ControlModule(
                key=f"{self.platform.value}.health",
                display_name="Health",
                platform=self.platform,
                capability=ModuleCapability.VIEW,
                status=ModuleStatus.AVAILABLE,
            ),
        )

    async def get_health(self, **kwargs):
        self.calls.append(("health", kwargs))
        return PlatformHealth(
            platform=self.platform,
            signals=(HealthSignal("api", "API", "ok", HealthStatus.OPERATIONAL, 10),),
        )

    async def get_dashboard(self, **kwargs):
        self.calls.append(("dashboard", kwargs))
        return PlatformDashboardSummary(
            platform=self.platform,
            messages_today=10,
            ai_flagged_today=1,
            creator_sources=2,
            bot_latency_ms=20,
        )

    async def verify_connection(self, **kwargs):
        self.calls.append(("verify", kwargs))
        return True


def call_args() -> dict[str, UUID]:
    return {
        "organization_id": uuid4(),
        "actor_id": uuid4(),
        "correlation_id": uuid4(),
    }


@pytest.mark.asyncio
async def test_registry_aggregates_modules_from_registered_platforms() -> None:
    discord = Adapter(Platform.DISCORD)
    twitch = Adapter(Platform.TWITCH)
    registry = PlatformControlRegistry((twitch, discord))
    args = call_args()

    modules = await registry.list_for_organization(**args)

    assert [module.platform for module in modules] == [Platform.DISCORD, Platform.TWITCH]
    assert registry.supported_platforms == (Platform.DISCORD, Platform.TWITCH)


@pytest.mark.asyncio
async def test_registry_routes_health_and_dashboard_to_selected_platform_only() -> None:
    discord = Adapter(Platform.DISCORD)
    twitch = Adapter(Platform.TWITCH)
    registry = PlatformControlRegistry((discord, twitch))
    args = call_args()

    health = await registry.get_for_organization(platform=Platform.TWITCH, **args)
    dashboard = await registry.get_for_connection(
        platform=Platform.TWITCH,
        external_resource_id="channel-1",
        **args,
    )

    assert health.platform is Platform.TWITCH
    assert dashboard.platform is Platform.TWITCH
    assert not any(name in {"health", "dashboard"} for name, _ in discord.calls)
    assert [name for name, _ in twitch.calls] == ["health", "dashboard"]


@pytest.mark.asyncio
async def test_registry_rejects_unsupported_platform_connection_without_network_call() -> None:
    registry = PlatformControlRegistry((Adapter(Platform.DISCORD),))
    args = call_args()

    verified = await registry.verify_registration(
        platform=Platform.TWITCH,
        external_resource_id="channel-1",
        **args,
    )

    assert verified is False


@pytest.mark.asyncio
async def test_registry_fails_closed_for_unsupported_read_adapter() -> None:
    registry = PlatformControlRegistry((Adapter(Platform.DISCORD),))

    with pytest.raises(PlatformControlUnavailableError):
        await registry.get_for_organization(platform=Platform.TWITCH, **call_args())


def test_registry_rejects_duplicate_platform_adapters() -> None:
    with pytest.raises(ValueError):
        PlatformControlRegistry((Adapter(Platform.DISCORD), Adapter(Platform.DISCORD)))
