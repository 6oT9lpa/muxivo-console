import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connection_reconciliation import ConnectionReconciliationReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.health import HealthStatus
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer
from muxivo_console.infrastructure.twitch_control_api import (
    TwitchPlatformConnectionReconciliationProbe,
    TwitchPlatformConnectionVerifier,
    TwitchPlatformHealthReader,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


class IdentityReader:
    def __init__(self, subject: str | None) -> None:
        self.subject = subject
        self.provider: LoginIdentityProvider | None = None

    async def find_provider_subject(
        self, *, user_id, provider: LoginIdentityProvider
    ) -> str | None:
        self.provider = provider
        return self.subject


def assertion_issuer() -> HmacControlAssertionIssuer:
    return HmacControlAssertionIssuer(
        issuer="muxivo-console",
        audience="muxivo-twitch-control",
        signing_key=b"t" * 32,
        clock=FixedClock(),
    )


def decode_claims(token: str) -> dict[str, object]:
    encoded_claims = token.split(".")[1]
    padding = "=" * (-len(encoded_claims) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded_claims + padding))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "target_status"),
    (
        ("token_expired", "reauth_required"),
        ("scopes_missing", "reauth_required"),
        ("preflight_failed", "degraded"),
    ),
)
async def test_twitch_reconciliation_probe_maps_control_decision(
    reason: str,
    target_status: str,
) -> None:
    system_actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None
    connection = PlatformConnection(
        id=uuid4(),
        organization_id=organization_id,
        platform=Platform.TWITCH,
        external_resource_id="broadcaster-123",
        status=ConnectionStatus.ACTIVE,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path == (
            f"/control/v1/organizations/{organization_id}/connections/"
            "broadcaster-123/reconciliation"
        )
        return httpx.Response(200, json={"target_status": target_status, "reason": reason})

    probe = TwitchPlatformConnectionReconciliationProbe(
        "http://twitch-control.test",
        assertion_issuer(),
        system_actor_id=system_actor_id,
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    decision = await probe.inspect_connection(
        connection=connection,
        correlation_id=correlation_id,
    )

    assert decision.target_status is ConnectionStatus(target_status)
    assert decision.reason is ConnectionReconciliationReason(reason)
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["aud"] == "muxivo-twitch-control"
    assert claims["resource"] == "console.platform_connections"
    assert claims["action"] == "read"
    assert claims["sub"] == str(system_actor_id)
    assert claims["platform_resource_id"] == "broadcaster-123"


@pytest.mark.asyncio
async def test_twitch_registration_verifier_maps_control_decision() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.method == "POST"
        assert request.url.path == (
            f"/control/v1/organizations/{organization_id}/connections/verify"
        )
        assert json.loads(request.content) == {
            "platform": "twitch",
            "external_resource_id": "broadcaster-123",
        }
        return httpx.Response(200, json={"verified": True})

    identities = IdentityReader("twitch-user-42")
    verifier = TwitchPlatformConnectionVerifier(
        "http://twitch-control.test",
        assertion_issuer(),
        identities,
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    verified = await verifier.verify_registration(
        actor_id=actor_id,
        organization_id=organization_id,
        platform=Platform.TWITCH,
        external_resource_id="broadcaster-123",
        correlation_id=correlation_id,
    )

    assert verified is True
    assert identities.provider is LoginIdentityProvider.TWITCH
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["aud"] == "muxivo-twitch-control"
    assert claims["resource"] == "console.platform_connections"
    assert claims["action"] == "manage"
    assert claims["sub"] == str(actor_id)
    assert claims["platform_subject"] == "twitch-user-42"


@pytest.mark.asyncio
async def test_twitch_health_reader_maps_browser_safe_control_signals() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.url.path == f"/control/v1/organizations/{organization_id}/health"
        return httpx.Response(
            200,
            json={
                "signals": [
                    {
                        "name": "Twitch EventSub",
                        "value": "Connected",
                        "status": "operational",
                        "latency_ms": 38,
                    },
                    {
                        "name": "OAuth scopes",
                        "value": "Missing chat:read",
                        "status": "degraded",
                    },
                ]
            },
        )

    reader = TwitchPlatformHealthReader(
        "http://twitch-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    health = await reader.get_for_organization(
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    assert health.platform is Platform.TWITCH
    assert [signal.key for signal in health.signals] == [
        "twitch.twitch-eventsub",
        "twitch.oauth-scopes",
    ]
    assert health.signals[0].status is HealthStatus.OPERATIONAL
    assert health.signals[0].latency_ms == 38
    assert health.signals[1].status is HealthStatus.DEGRADED
    assert health.signals[1].latency_ms is None
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["aud"] == "muxivo-twitch-control"
    assert claims["resource"] == "console.control_modules"
    assert claims["action"] == "read"
    assert claims["sub"] == str(actor_id)


@pytest.mark.asyncio
async def test_twitch_health_reader_rejects_invalid_health_payload() -> None:
    reader = TwitchPlatformHealthReader(
        "http://twitch-control.test",
        assertion_issuer(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"signals": [{"name": "EventSub"}]})
        ),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="health signal"):
        await reader.get_for_organization(
            organization_id=uuid4(),
            actor_id=uuid4(),
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_twitch_registration_verifier_requires_linked_twitch_identity() -> None:
    network_called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal network_called
        network_called = True
        return httpx.Response(200, json={"verified": True})

    verifier = TwitchPlatformConnectionVerifier(
        "http://twitch-control.test",
        assertion_issuer(),
        IdentityReader(None),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    verified = await verifier.verify_registration(
        actor_id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.TWITCH,
        external_resource_id="broadcaster-123",
        correlation_id=uuid4(),
    )

    assert verified is False
    assert network_called is False


@pytest.mark.asyncio
async def test_twitch_registration_verifier_rejects_invalid_control_payload() -> None:
    verifier = TwitchPlatformConnectionVerifier(
        "http://twitch-control.test",
        assertion_issuer(),
        IdentityReader("twitch-user-42"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"ok": True})),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="verification payload"):
        await verifier.verify_registration(
            actor_id=uuid4(),
            organization_id=uuid4(),
            platform=Platform.TWITCH,
            external_resource_id="broadcaster-123",
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_twitch_reconciliation_probe_ignores_other_platform_connections() -> None:
    probe = TwitchPlatformConnectionReconciliationProbe(
        "https://twitch-control.test",
        assertion_issuer(),
        system_actor_id=uuid4(),
    )
    connection = PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=ConnectionStatus.DEGRADED,
    )

    decision = await probe.inspect_connection(connection=connection, correlation_id=uuid4())

    assert decision.target_status is ConnectionStatus.DEGRADED
    assert decision.reason is ConnectionReconciliationReason.HEALTHY


@pytest.mark.asyncio
async def test_twitch_reconciliation_probe_rejects_invalid_control_payload() -> None:
    probe = TwitchPlatformConnectionReconciliationProbe(
        "http://twitch-control.test",
        assertion_issuer(),
        system_actor_id=uuid4(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"target_status": "active"})
        ),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match="reconciliation decision"):
        await probe.inspect_connection(
            connection=PlatformConnection(
                id=uuid4(),
                organization_id=uuid4(),
                platform=Platform.TWITCH,
                external_resource_id="broadcaster-123",
                status=ConnectionStatus.ACTIVE,
            ),
            correlation_id=uuid4(),
        )


def test_twitch_control_api_requires_https_outside_development() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        TwitchPlatformConnectionReconciliationProbe(
            "http://twitch-control.test",
            assertion_issuer(),
            system_actor_id=uuid4(),
        )
