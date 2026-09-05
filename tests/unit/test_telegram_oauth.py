import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from muxivo_console.infrastructure.openid_connect_oauth_unavailable_error import (
    OpenIdConnectOAuthUnavailableError,
)
from muxivo_console.infrastructure.telegram_oauth import TelegramOAuthClient

NOW = 2_000_000_000.0


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _signed_id_token(
    private_key: rsa.RSAPrivateKey,
    *,
    audience: str = "telegram-client-id",
    expires_at: float = NOW + 300,
    key_id: str = "telegram-key-1",
) -> str:
    header = {"alg": "RS256", "kid": key_id, "typ": "JWT"}
    claims = {
        "iss": "https://oauth.telegram.org",
        "aud": audience,
        "sub": "telegram-subject",
        "iat": NOW,
        "exp": expires_at,
    }
    encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_claims = _base64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode()
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


def _client(
    transport: httpx.AsyncBaseTransport,
    *,
    clock=lambda: NOW,
) -> TelegramOAuthClient:
    return TelegramOAuthClient(
        client_id="telegram-client-id",
        client_secret="telegram-client-secret",
        redirect_uri="https://console.muxivo.example/api/v1/auth/telegram/callback",
        transport=transport,
        clock=clock,
    )


def test_authorization_url_contains_pkce_and_minimal_telegram_oidc_scope() -> None:
    client = TelegramOAuthClient(
        client_id="telegram-client-id",
        client_secret="telegram-client-secret",
        redirect_uri="https://console.muxivo.example/api/v1/auth/telegram/callback",
    )

    query = parse_qs(
        urlparse(client.authorization_url(state="state", code_challenge="challenge")).query
    )

    assert query == {
        "client_id": ["telegram-client-id"],
        "redirect_uri": ["https://console.muxivo.example/api/v1/auth/telegram/callback"],
        "response_type": ["code"],
        "scope": ["openid profile"],
        "state": ["state"],
        "code_challenge": ["challenge"],
        "code_challenge_method": ["S256"],
    }


@pytest.mark.asyncio
async def test_exchanges_code_and_verifies_telegram_jwks_signed_id_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    id_token = _signed_id_token(private_key)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            assert request.headers["Authorization"].startswith("Basic ")
            assert b"code=authorization-code" in request.content
            assert b"code_verifier=pkce-verifier" in request.content
            return httpx.Response(200, json={"id_token": id_token, "access_token": "never-used"})
        assert request.url.path == "/.well-known/jwks.json"
        return httpx.Response(
            200,
            json={
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "telegram-key-1",
                        "use": "sig",
                        "alg": "RS256",
                        "n": _base64url(
                            public_numbers.n.to_bytes(
                                (public_numbers.n.bit_length() + 7) // 8, "big"
                            )
                        ),
                        "e": _base64url(
                            public_numbers.e.to_bytes(
                                (public_numbers.e.bit_length() + 7) // 8, "big"
                            )
                        ),
                    }
                ]
            },
        )

    subject = await _client(httpx.MockTransport(handler)).resolve_subject(
        authorization_code="authorization-code", code_verifier="pkce-verifier"
    )

    assert subject == "telegram-subject"


@pytest.mark.asyncio
async def test_rejects_tampered_or_expired_telegram_id_tokens() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    valid_token = _signed_id_token(private_key)
    tampered_token = f"{valid_token[:-2]}aa"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"id_token": tampered_token})
        return httpx.Response(
            200,
            json={
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "telegram-key-1",
                        "n": _base64url(
                            public_numbers.n.to_bytes(
                                (public_numbers.n.bit_length() + 7) // 8, "big"
                            )
                        ),
                        "e": _base64url(
                            public_numbers.e.to_bytes(
                                (public_numbers.e.bit_length() + 7) // 8, "big"
                            )
                        ),
                    }
                ]
            },
        )

    with pytest.raises(OpenIdConnectOAuthUnavailableError):
        await _client(httpx.MockTransport(handler)).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )

    expired_token = _signed_id_token(private_key, expires_at=NOW - 1)

    def expired_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"id_token": expired_token})
        return handler(request)

    with pytest.raises(OpenIdConnectOAuthUnavailableError):
        await _client(httpx.MockTransport(expired_handler)).resolve_subject(
            authorization_code="code", code_verifier="verifier"
        )


def test_telegram_adapter_does_not_accept_a_non_https_callback() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        TelegramOAuthClient(
            client_id="telegram-client-id",
            client_secret="telegram-client-secret",
            redirect_uri="http://console.example/callback",
        )
