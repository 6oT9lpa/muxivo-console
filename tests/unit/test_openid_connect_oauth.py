from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from muxivo_console.infrastructure.openid_connect_oauth import OpenIdConnectOAuthClient
from muxivo_console.infrastructure.openid_connect_oauth_unavailable_error import (
    OpenIdConnectOAuthUnavailableError,
)


def client(
    transport: httpx.AsyncBaseTransport | None = None,
    *,
    subject_field: str = "sub",
) -> OpenIdConnectOAuthClient:
    return OpenIdConnectOAuthClient(
        provider_label="Google",
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://console.muxivo.example/api/v1/auth/google/callback",
        authorize_url="https://google-id.test/oauth/authorize",
        token_url="https://google-id.test/oauth/token",
        userinfo_url="https://google-id.test/userinfo",
        scopes=("openid", "email", "profile"),
        subject_field=subject_field,
        transport=transport,
    )


def test_authorization_url_contains_pkce_and_configured_oidc_scopes() -> None:
    query = parse_qs(
        urlparse(client().authorization_url(state="opaque-state", code_challenge="challenge")).query
    )

    assert query == {
        "client_id": ["client-id"],
        "redirect_uri": ["https://console.muxivo.example/api/v1/auth/google/callback"],
        "response_type": ["code"],
        "scope": ["openid email profile"],
        "state": ["opaque-state"],
        "code_challenge": ["challenge"],
        "code_challenge_method": ["S256"],
    }


@pytest.mark.asyncio
async def test_exchanges_code_server_side_and_returns_only_oidc_subject() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            assert b"code_verifier=pkce-verifier" in request.content
            assert b"code=authorization-code" in request.content
            return httpx.Response(200, json={"access_token": "provider-access-token"})
        assert request.url == "https://google-id.test/userinfo"
        assert request.headers["Authorization"] == "Bearer provider-access-token"
        return httpx.Response(200, json={"sub": "google-subject", "email": "private@example.com"})

    subject = await client(httpx.MockTransport(handler)).resolve_subject(
        authorization_code="authorization-code", code_verifier="pkce-verifier"
    )

    assert subject == "google-subject"


@pytest.mark.asyncio
async def test_supports_yandex_subject_field_without_returning_provider_profile() -> None:
    yandex_client = client(subject_field="id")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "yandex-access-token"})
        return httpx.Response(200, json={"id": "yandex-subject", "login": "private-login"})

    subject = await client(httpx.MockTransport(handler), subject_field="id").resolve_subject(
        authorization_code="code", code_verifier="verifier"
    )

    assert subject == "yandex-subject"
    assert yandex_client.subject_field == "id"


@pytest.mark.asyncio
async def test_rejects_missing_token_and_invalid_subject() -> None:
    with pytest.raises(OpenIdConnectOAuthUnavailableError):
        await client(httpx.MockTransport(lambda _: httpx.Response(200, json={}))).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(200, json={"sub": ""})

    with pytest.raises(OpenIdConnectOAuthUnavailableError):
        await client(httpx.MockTransport(handler)).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )
