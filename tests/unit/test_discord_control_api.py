import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
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


@pytest.mark.asyncio
async def test_discord_verifier_rejects_other_platforms_without_http_call() -> None:
    verifier = DiscordPlatformConnectionVerifier(
        "http://discord-control.test",
        assertion_issuer(),
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
