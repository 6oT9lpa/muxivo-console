import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation_policy import (
    PlatformAiModerationPolicy,
)
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.channel_purposes import ChannelPurpose
from muxivo_console.domain.welcome import PlatformWelcomeSettings
from muxivo_console.infrastructure.discord_control_api import (
    DiscordControlApiCatalog,
    DiscordPlatformConnectionVerifier,
    HmacControlAssertionIssuer,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def assertion_issuer() -> HmacControlAssertionIssuer:
    return HmacControlAssertionIssuer(
        issuer="muxivo-console",
        audience="muxivo-discord-control",
        signing_key=b"a" * 32,
        clock=FixedClock(),
    )


class Identities:
    def __init__(self, subject: str | None = "123456789012345678") -> None:
        self.subject = subject
        self.arguments = None

    async def find_provider_subject(self, **arguments) -> str | None:
        self.arguments = arguments
        return self.subject


def decode_claims(token: str) -> dict[str, object]:
    encoded_claims = token.split(".")[1]
    padding = "=" * (-len(encoded_claims) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded_claims + padding))


def test_assertion_is_short_lived_and_binds_exact_console_request_facts() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()

    token = assertion_issuer().issue(
        actor_id=actor_id,
        organization_id=organization_id,
        resource=AuthorizationResource.CONTROL_MODULES,
        action=AuthorizationAction.READ,
        correlation_id=correlation_id,
    )

    claims = decode_claims(token)
    assert claims["iss"] == "muxivo-console"
    assert claims["aud"] == "muxivo-discord-control"
    assert claims["sub"] == str(actor_id)
    assert claims["organization_id"] == str(organization_id)
    assert claims["resource"] == "console.control_modules"
    assert claims["action"] == "read"
    assert claims["correlation_id"] == str(correlation_id)
    assert claims["exp"] == claims["iat"] + 60
    assert isinstance(claims["jti"], str)


def test_assertion_can_bind_one_platform_resource() -> None:
    token = assertion_issuer().issue(
        actor_id=uuid4(),
        organization_id=uuid4(),
        resource=AuthorizationResource.CONTROL_MODULES,
        action=AuthorizationAction.READ,
        correlation_id=uuid4(),
        platform_resource_id="123456789012345678",
    )

    assert decode_claims(token)["platform_resource_id"] == "123456789012345678"


@pytest.mark.asyncio
async def test_catalog_calls_versioned_discord_api_with_bound_assertion() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path == f"/control/v1/organizations/{organization_id}/modules"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "key": "discord.logs",
                        "display_name": "Audit log",
                        "platform": "discord",
                        "capability": "view",
                        "status": "available",
                    }
                ]
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        Identities(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    modules = await catalog.list_for_organization(
        actor_id=actor_id, organization_id=organization_id, correlation_id=correlation_id
    )

    assert modules[0].key == "discord.logs"
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["sub"] == str(actor_id)
    assert claims["organization_id"] == str(organization_id)
    assert claims["correlation_id"] == str(correlation_id)


@pytest.mark.asyncio
async def test_catalog_rejects_bad_platform_payload_without_leaking_upstream_details() -> None:
    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"items": [{}]})),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="invalid module"):
        await catalog.list_for_organization(
            actor_id=uuid4(), organization_id=uuid4(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_catalog_reads_assertion_bound_non_secret_bot_settings() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    resource_id = "123456789012345678"
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path.endswith(f"/connections/{resource_id}/bot-settings")
        return httpx.Response(
            200,
            json={
                "settings": {
                    "subscription_tier": "plus",
                    "activity_rotation_enabled": True,
                    "activity_rotation_interval_seconds": 60,
                    "retention": {"message_log_retention_days": 30},
                }
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    settings = await catalog.get_bot_settings_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=resource_id,
        correlation_id=correlation_id,
    )

    assert settings.subscription_tier == "plus"
    assert settings.retention_days == (("message_log_retention_days", 30),)
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["platform_subject"] == "123456789012345678"
    assert claims["platform_resource_id"] == resource_id


@pytest.mark.asyncio
async def test_catalog_reads_assertion_bound_secret_free_integrations() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    resource_id = "123456789012345678"
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path.endswith(f"/connections/{resource_id}/integrations")
        return httpx.Response(
            200,
            json={
                "integrations": {
                    "discord_bot": {"status": "configured"},
                    "creator_platforms": {
                        "status": "configured",
                        "poll_interval_seconds": 60,
                        "sources": [{"platform": "twitch", "count": 2, "active_count": 1}],
                    },
                    "muxivo_core": {"status": "configured"},
                    "database": {"status": "configured"},
                }
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    integrations = await catalog.get_integrations_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=resource_id,
        correlation_id=correlation_id,
    )

    assert integrations.creator_sources[0].active == 1
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["platform_subject"] == "123456789012345678"
    assert claims["platform_resource_id"] == resource_id


@pytest.mark.asyncio
async def test_catalog_maps_aggregate_discord_health_without_platform_secrets() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/control/v1/organizations/{organization_id}/health"
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["resource"] == "console.control_modules"
        assert claims["action"] == "read"
        return httpx.Response(
            200,
            json={
                "signals": [
                    {
                        "name": "Bot latency",
                        "value": "12 ms",
                        "status": "operational",
                        "latency_ms": 12,
                    }
                ]
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    health = await catalog.get_for_organization(
        actor_id=actor_id,
        organization_id=organization_id,
        correlation_id=correlation_id,
    )

    assert health.platform is Platform.DISCORD
    assert health.signals[0].key == "discord.bot-latency"
    assert health.signals[0].latency_ms == 12


@pytest.mark.asyncio
async def test_catalog_rejects_invalid_discord_health_payload() -> None:
    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"signals": [{}]})),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="invalid health signal"):
        await catalog.get_for_organization(
            actor_id=uuid4(), organization_id=uuid4(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_catalog_binds_dashboard_request_to_one_discord_resource() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.path
            == f"/control/v1/organizations/{organization_id}/connections/{guild_id}/dashboard"
        )
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_resource_id"] == guild_id
        return httpx.Response(
            200,
            json={
                "guild_id": guild_id,
                "metrics": {
                    "messages_today": 42,
                    "ai_flagged_today": 3,
                    "creator_sources": 2,
                    "bot_latency_ms": 12,
                },
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    summary = await catalog.get_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
    )

    assert summary.messages_today == 42
    assert summary.bot_latency_ms == 12


@pytest.mark.asyncio
async def test_catalog_binds_channel_request_to_one_discord_resource() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.path
            == f"/control/v1/organizations/{organization_id}/connections/{guild_id}/channels"
        )
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_resource_id"] == guild_id
        return httpx.Response(
            200,
            json={
                "guild_id": guild_id,
                "items": [
                    {"id": "10", "name": "general", "kind": "text"},
                    {"id": "11", "name": "voice", "kind": "voice"},
                ],
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    channels = await catalog.get_channel_catalog_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
    )

    assert channels.platform is Platform.DISCORD
    assert [(item.id, item.kind) for item in channels.items] == [
        ("10", "text"),
        ("11", "voice"),
    ]


@pytest.mark.asyncio
async def test_catalog_reads_ai_moderation_summary_for_one_discord_resource() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/{guild_id}/ai-moderation-summary")
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_resource_id"] == guild_id
        return httpx.Response(200, json={"summary": ai_moderation_summary_payload()})

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )
    summary = await catalog.get_ai_moderation_summary_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
    )

    assert summary.enforcement_mode == "SHADOW"
    assert summary.covered_channel_count == 2
    assert summary.automated_ban_enabled is False


@pytest.mark.asyncio
async def test_catalog_binds_welcome_settings_request_to_one_discord_resource() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        expected_path = (
            f"/control/v1/organizations/{organization_id}/connections/{guild_id}/welcome-settings"
        )
        assert request.url.path == expected_path
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_resource_id"] == guild_id
        return httpx.Response(
            200,
            json={
                "guild_id": guild_id,
                "settings": {
                    "title": "Welcome!",
                    "description": "Hi, {user}!",
                    "thumbnail_url": None,
                    "footer_text": "Be kind",
                    "footer_icon_url": None,
                    "color": 5769984,
                    "is_enabled": True,
                    "rules_channel_id": "10",
                    "roles_channel_id": None,
                },
            },
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    settings = await catalog.get_welcome_settings_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
    )

    assert settings.platform is Platform.DISCORD
    assert settings.title == "Welcome!"
    assert settings.rules_channel_id == "10"


@pytest.mark.asyncio
async def test_catalog_updates_welcome_settings_with_linked_discord_identity() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path.endswith(f"/{guild_id}/welcome-settings")
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_subject"] == "123456789012345678"
        assert json.loads(request.content)["rules_channel_id"] == 10
        return httpx.Response(200, json={"settings": welcome_payload()})

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    result = await catalog.update_welcome_settings_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
        settings=welcome_settings(),
    )

    assert result.title == "Welcome!"


@pytest.mark.asyncio
async def test_catalog_updates_channel_purpose_with_a_resource_bound_identity() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path.endswith(f"/{guild_id}/channel-purposes")
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_subject"] == "123456789012345678"
        assert claims["platform_resource_id"] == guild_id
        assert json.loads(request.content) == {"purpose": "welcome", "channel_id": 10}
        return httpx.Response(200, json={"guild_id": guild_id, "items": {"welcome": "10"}})

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    result = await catalog.update_channel_purpose_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
        purpose=ChannelPurpose.WELCOME,
        channel_id="10",
    )

    assert result.assignments == {ChannelPurpose.WELCOME: "10"}


@pytest.mark.asyncio
async def test_catalog_updates_ai_moderation_policy_with_bound_discord_identity() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path.endswith(f"/{guild_id}/ai-moderation-policy")
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_subject"] == "123456789012345678"
        assert claims["platform_resource_id"] == guild_id
        policy = json.loads(request.content)["policy"]
        assert policy["excluded_channel_ids"] == [10]
        assert policy["enforcement_mode"] == "SHADOW"
        return httpx.Response(200, json={"summary": ai_moderation_summary_payload()})

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    result = await catalog.update_ai_moderation_policy_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
        policy=PlatformAiModerationPolicy(
            platform=Platform.DISCORD,
            excluded_channel_ids=("10",),
        ),
    )

    assert result.enforcement_mode == "SHADOW"


@pytest.mark.asyncio
async def test_catalog_reads_effective_ai_moderation_policy_with_bound_identity() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    guild_id = "123456789012345678"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith(f"/{guild_id}/ai-moderation-policy")
        claims = decode_claims(request.headers["Authorization"].removeprefix("Bearer "))
        assert claims["platform_subject"] == "123456789012345678"
        assert claims["platform_resource_id"] == guild_id
        return httpx.Response(
            200,
            json={"policy": ai_moderation_policy_payload(), "is_default_policy": True},
        )

    catalog = DiscordControlApiCatalog(
        "http://discord-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
        identities=Identities(),
    )
    state = await catalog.get_ai_moderation_policy_for_connection(
        actor_id=actor_id,
        organization_id=organization_id,
        external_resource_id=guild_id,
        correlation_id=correlation_id,
    )

    assert state.is_default_policy is True
    assert state.policy.labels["SPAM"].risk_threshold == 25


def welcome_settings() -> PlatformWelcomeSettings:
    return PlatformWelcomeSettings(
        Platform.DISCORD, "Welcome!", "Hi, {user}!", None, None, None, 5769984, True, "10", None
    )


def ai_moderation_summary_payload() -> dict[str, object]:
    return {
        "enforcement_mode": "SHADOW",
        "test_mode": False,
        "is_default_policy": True,
        "covered_channel_count": 2,
        "log_channel_configured": True,
        "label_count": 8,
        "blacklist_word_count": 0,
        "allowed_domain_count": 0,
        "automated_timeout_enabled": False,
        "automated_kick_enabled": False,
        "automated_ban_enabled": False,
    }


def ai_moderation_policy_payload() -> dict[str, object]:
    return {
        "blacklist_words": [],
        "allowed_domains": [],
        "labels": {"SPAM": {"risk_threshold": 25, "min_action": "LOG", "max_action": "DELETE"}},
        "blacklist_action": "DELETE_WARN",
        "unapproved_domain_action": "REVIEW",
        "context_window_days": 30,
        "repeat_offender_threshold": 3,
        "repeat_offender_action": "TIMEOUT",
        "escalation_enabled": True,
        "escalation_score_threshold": 3,
        "escalation_half_life_days": 30,
        "excluded_user_ids": [],
        "excluded_role_ids": [],
        "excluded_channel_ids": [],
        "exclude_bots": True,
        "ocr_enabled": False,
        "ocr_failure_mode": "SKIP",
        "ocr_max_gif_frames": 6,
        "ocr_process_empty_result": False,
        "test_mode": False,
        "enforcement_mode": "SHADOW",
        "limited_min_confidence": 0.95,
        "limited_hard_rule_labels": ["INVITE", "SCAM"],
        "beta_enforcement_acknowledged": False,
        "allow_automated_timeout": False,
        "allow_automated_kick": False,
        "allow_automated_ban": False,
    }


def welcome_payload() -> dict[str, object]:
    return {
        "title": "Welcome!",
        "description": "Hi, {user}!",
        "thumbnail_url": None,
        "footer_text": None,
        "footer_icon_url": None,
        "color": 5769984,
        "is_enabled": True,
        "rules_channel_id": "10",
        "roles_channel_id": None,
    }


def test_catalog_requires_https_outside_explicit_local_development() -> None:
    with pytest.raises(ValueError, match="absolute service URL"):
        DiscordControlApiCatalog("http://discord-control.test", assertion_issuer())


def test_assertion_rejects_weak_shared_secret() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        HmacControlAssertionIssuer(
            issuer="muxivo-console",
            audience="muxivo-discord-control",
            signing_key=b"weak",
            clock=FixedClock(),
        )


@pytest.mark.asyncio
async def test_discord_verifier_requires_platform_confirmation_with_manage_assertion() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path == f"/control/v1/organizations/{organization_id}/connections/verify"
        assert json.loads(request.content) == {
            "platform": "discord",
            "external_resource_id": "123456789012345678",
        }
        return httpx.Response(200, json={"verified": True})

    verifier = DiscordPlatformConnectionVerifier(
        "http://discord-control.test",
        assertion_issuer(),
        Identities(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    verified = await verifier.verify_registration(
        actor_id=actor_id,
        organization_id=organization_id,
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        correlation_id=correlation_id,
    )

    assert verified is True
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["resource"] == "console.platform_connections"
    assert claims["action"] == "manage"
    assert claims["sub"] == str(actor_id)
    assert claims["platform_subject"] == "123456789012345678"


@pytest.mark.asyncio
async def test_discord_verifier_rejects_other_platforms_without_http_call() -> None:
    verifier = DiscordPlatformConnectionVerifier(
        "http://discord-control.test",
        assertion_issuer(),
        Identities(),
        transport=httpx.MockTransport(lambda _: pytest.fail("unexpected HTTP call")),
        allow_insecure_http=True,
    )

    verified = await verifier.verify_registration(
        actor_id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.TWITCH,
        external_resource_id="channel-id",
        correlation_id=uuid4(),
    )

    assert verified is False


@pytest.mark.asyncio
async def test_discord_verifier_rejects_unlinked_console_user_without_http_call() -> None:
    verifier = DiscordPlatformConnectionVerifier(
        "http://discord-control.test",
        assertion_issuer(),
        Identities(None),
        transport=httpx.MockTransport(lambda _: pytest.fail("unexpected HTTP call")),
        allow_insecure_http=True,
    )

    verified = await verifier.verify_registration(
        actor_id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123",
        correlation_id=uuid4(),
    )

    assert verified is False
