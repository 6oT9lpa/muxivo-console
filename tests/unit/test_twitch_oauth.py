from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from muxivo_console.infrastructure.twitch_oauth import (
    TwitchOAuthClient,
    TwitchOAuthUnavailableError,
)


def client(transport: httpx.AsyncBaseTransport | None = None) -> TwitchOAuthClient:
    return TwitchOAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://console.muxivo.example/api/v1/auth/twitch/callback",
        api_base_url="https://twitch-api.test/helix",
        token_url="https://twitch-id.test/oauth2/token",
        authorize_url="https://twitch-id.test/oauth2/authorize",
        transport=transport,
    )


def test_authorization_url_requires_pkce_state_and_minimal_twitch_identity_scope() -> None:
    query = parse_qs(
        urlparse(client().authorization_url(state="opaque-state", code_challenge="challenge")).query
    )

    assert query == {
        "client_id": ["client-id"],
        "redirect_uri": ["https://console.muxivo.example/api/v1/auth/twitch/callback"],
        "response_type": ["code"],
        "scope": ["user:read:email"],
        "state": ["opaque-state"],
        "code_challenge": ["challenge"],
        "code_challenge_method": ["S256"],
    }


@pytest.mark.asyncio
async def test_exchanges_code_server_side_and_returns_only_verified_twitch_subject() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "twitch-id.test":
            assert request.url.path == "/oauth2/token"
            assert b"code_verifier=pkce-verifier" in request.content
            assert b"code=authorization-code" in request.content
            return httpx.Response(200, json={"access_token": "twitch-access-token"})
        assert request.url == "https://twitch-api.test/helix/users"
        assert request.headers["Authorization"] == "Bearer twitch-access-token"
        assert request.headers["Client-Id"] == "client-id"
        return httpx.Response(200, json={"data": [{"id": "123456789"}]})

    subject = await client(httpx.MockTransport(handler)).resolve_subject(
        authorization_code="authorization-code", code_verifier="pkce-verifier"
    )

    assert subject == "123456789"


@pytest.mark.asyncio
async def test_refuses_missing_token_or_invalid_helix_subject() -> None:
    bad_token = client(httpx.MockTransport(lambda _: httpx.Response(200, json={})))
    with pytest.raises(TwitchOAuthUnavailableError):
        await bad_token.resolve_subject(authorization_code="code", code_verifier="verifier")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "twitch-id.test":
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(200, json={"data": [{"id": "not-a-twitch-id"}]})

    with pytest.raises(TwitchOAuthUnavailableError):
        await client(httpx.MockTransport(handler)).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )
