from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from muxivo_console.infrastructure.discord_oauth import (
    DiscordOAuthClient,
    DiscordOAuthUnavailableError,
)


def client(transport: httpx.AsyncBaseTransport | None = None) -> DiscordOAuthClient:
    return DiscordOAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://console.muxivo.example/api/v1/identity-links/discord/callback",
        api_base_url="https://discord.test",
        authorize_url="https://discord.test/oauth2/authorize",
        transport=transport,
    )


def test_authorization_url_requires_pkce_state_and_only_required_discord_scopes() -> None:
    query = parse_qs(
        urlparse(client().authorization_url(state="opaque-state", code_challenge="challenge")).query
    )

    assert query == {
        "client_id": ["client-id"],
        "redirect_uri": ["https://console.muxivo.example/api/v1/identity-links/discord/callback"],
        "response_type": ["code"],
        "scope": ["identify guilds"],
        "state": ["opaque-state"],
        "code_challenge": ["challenge"],
        "code_challenge_method": ["S256"],
    }


@pytest.mark.asyncio
async def test_exchanges_code_server_side_and_returns_only_verified_discord_subject() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            assert b"code_verifier=pkce-verifier" in request.content
            assert b"code=authorization-code" in request.content
            return httpx.Response(200, json={"access_token": "discord-access-token"})
        assert request.url.path == "/users/@me"
        assert request.headers["Authorization"] == "Bearer discord-access-token"
        return httpx.Response(200, json={"id": "123456789012345678", "username": "Creator"})

    subject = await client(httpx.MockTransport(handler)).resolve_subject(
        authorization_code="authorization-code", code_verifier="pkce-verifier"
    )

    assert subject == "123456789012345678"


@pytest.mark.asyncio
async def test_refuses_missing_token_or_non_snowflake_subject() -> None:
    bad_token = client(httpx.MockTransport(lambda _: httpx.Response(200, json={})))
    with pytest.raises(DiscordOAuthUnavailableError):
        await bad_token.resolve_subject(authorization_code="code", code_verifier="verifier")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(200, json={"id": "not-a-discord-id"})

    with pytest.raises(DiscordOAuthUnavailableError):
        await client(httpx.MockTransport(handler)).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )
