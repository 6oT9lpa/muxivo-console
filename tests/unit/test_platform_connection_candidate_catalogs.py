import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.infrastructure.discord_connection_candidate_catalog import (
    DiscordPlatformConnectionCandidateCatalog,
)
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer
from muxivo_console.infrastructure.twitch_connection_candidate_catalog import (
    TwitchPlatformConnectionCandidateCatalog,
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


def issuer(audience: str) -> HmacControlAssertionIssuer:
    return HmacControlAssertionIssuer(
        issuer="muxivo-console",
        audience=audience,
        signing_key=b"c" * 32,
        clock=FixedClock(),
    )


def decode_claims(token: str) -> dict[str, object]:
    encoded_claims = token.split(".")[1]
    padding = "=" * (-len(encoded_claims) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded_claims + padding))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("catalog_type", "platform", "provider", "audience", "subject"),
    (
        (
            DiscordPlatformConnectionCandidateCatalog,
            Platform.DISCORD,
            LoginIdentityProvider.DISCORD,
            "muxivo-discord-control",
            "discord-user-42",
        ),
        (
            TwitchPlatformConnectionCandidateCatalog,
            Platform.TWITCH,
            LoginIdentityProvider.TWITCH,
            "muxivo-twitch-control",
            "twitch-user-42",
        ),
    ),
)
async def test_catalog_lists_owned_resources_with_bound_manage_assertion(
    catalog_type,
    platform: Platform,
    provider: LoginIdentityProvider,
    audience: str,
    subject: str,
) -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    received_authorization: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_authorization
        received_authorization = request.headers["Authorization"]
        assert request.method == "GET"
        assert request.url.path == (
            f"/control/v1/organizations/{organization_id}/connection-candidates"
        )
        assert request.url.params["platform"] == platform.value
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "external_resource_id": "resource-42",
                        "display_name": "Owned resource",
                    }
                ]
            },
        )

    catalog = catalog_type(
        "http://control.test",
        issuer(audience),
        IdentityReader(subject),
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    result = await catalog.list_for_organization(
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    assert result.platform is platform
    assert result.identity_linked is True
    assert result.items[0].external_resource_id == "resource-42"
    assert result.items[0].display_name == "Owned resource"
    assert received_authorization is not None
    claims = decode_claims(received_authorization.removeprefix("Bearer "))
    assert claims["aud"] == audience
    assert claims["resource"] == "console.platform_connections"
    assert claims["action"] == "manage"
    assert claims["sub"] == str(actor_id)
    assert claims["organization_id"] == str(organization_id)
    assert claims["platform_subject"] == subject


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("catalog_type", "platform", "provider", "audience"),
    (
        (
            DiscordPlatformConnectionCandidateCatalog,
            Platform.DISCORD,
            LoginIdentityProvider.DISCORD,
            "muxivo-discord-control",
        ),
        (
            TwitchPlatformConnectionCandidateCatalog,
            Platform.TWITCH,
            LoginIdentityProvider.TWITCH,
            "muxivo-twitch-control",
        ),
    ),
)
async def test_catalog_returns_empty_unlinked_state_without_network_call(
    catalog_type,
    platform: Platform,
    provider: LoginIdentityProvider,
    audience: str,
) -> None:
    network_called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal network_called
        network_called = True
        return httpx.Response(200, json={"items": []})

    identity_reader = IdentityReader(None)
    catalog = catalog_type(
        "http://control.test",
        issuer(audience),
        identity_reader,
        transport=httpx.MockTransport(handler),
        allow_insecure_http=True,
    )

    result = await catalog.list_for_organization(
        organization_id=uuid4(), actor_id=uuid4(), correlation_id=uuid4()
    )

    assert result.platform is platform
    assert result.items == ()
    assert result.identity_linked is False
    assert identity_reader.provider is provider
    assert network_called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("catalog_type", "audience", "message"),
    (
        (
            DiscordPlatformConnectionCandidateCatalog,
            "muxivo-discord-control",
            "Discord Control API",
        ),
        (
            TwitchPlatformConnectionCandidateCatalog,
            "muxivo-twitch-control",
            "Twitch Control API",
        ),
    ),
)
async def test_catalog_rejects_malformed_upstream_candidate_payload(
    catalog_type, audience: str, message: str
) -> None:
    catalog = catalog_type(
        "http://control.test",
        issuer(audience),
        IdentityReader("platform-user"),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"items": [{"display_name": "Missing ID"}]})
        ),
        allow_insecure_http=True,
    )

    with pytest.raises(PlatformControlUnavailableError, match=message):
        await catalog.list_for_organization(
            organization_id=uuid4(), actor_id=uuid4(), correlation_id=uuid4()
        )
