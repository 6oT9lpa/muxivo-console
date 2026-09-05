"""Server-side Telegram Login OIDC adapter.

Telegram returns a signed ID token instead of a user-info endpoint in the
manual OIDC flow. The adapter therefore keeps the complete verification
boundary on the API: code exchange, JWKS lookup, signature validation and
claim validation all happen before only the stable provider subject leaves the
infrastructure layer.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from muxivo_console.infrastructure.openid_connect_oauth_unavailable_error import (
    OpenIdConnectOAuthUnavailableError,
)

logger = logging.getLogger("muxivo_console.infrastructure.telegram_oauth")

_TELEGRAM_ISSUER: Final = "https://oauth.telegram.org"
_TELEGRAM_AUTHORIZE_URL: Final = "https://oauth.telegram.org/auth"
_TELEGRAM_TOKEN_URL: Final = "https://oauth.telegram.org/token"
_TELEGRAM_JWKS_URL: Final = "https://oauth.telegram.org/.well-known/jwks.json"
_MAX_CLOCK_SKEW_SECONDS: Final = 60.0


@dataclass(frozen=True, slots=True)
class TelegramOAuthClient:
    """Exchange Telegram authorization codes and return only a verified subject."""

    client_id: str
    client_secret: str
    redirect_uri: str
    timeout: float = 10.0
    transport: httpx.AsyncBaseTransport | None = None
    clock: Callable[[], float] = time.time

    def __post_init__(self) -> None:
        if (
            not self.client_id
            or not self.client_secret
            or not self.redirect_uri.startswith("https://")
        ):
            raise ValueError("Telegram OAuth credentials and an HTTPS callback are required.")

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        """Build a PKCE authorization URL without exposing any client secret."""
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "openid profile",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{_TELEGRAM_AUTHORIZE_URL}?{query}"

    async def resolve_subject(self, *, authorization_code: str, code_verifier: str) -> str:
        """Validate Telegram's signed ID token and return its stable subject."""
        logger.info(
            "auth.telegram_oauth.token_exchange.started",
            extra={"has_authorization_code": bool(authorization_code)},
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                token_response = await client.post(
                    _TELEGRAM_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self.redirect_uri,
                        "client_id": self.client_id,
                        "code_verifier": code_verifier,
                    },
                    auth=(self.client_id, self.client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                token_response.raise_for_status()
                token_payload = _json_object(token_response.json())
                id_token = token_payload.get("id_token")
                if not isinstance(id_token, str) or not id_token:
                    raise ValueError("Telegram token response did not contain an ID token.")
                logger.info("auth.telegram_oauth.token_exchange.completed")

                jwks_response = await client.get(_TELEGRAM_JWKS_URL)
                jwks_response.raise_for_status()
                jwks_payload = _json_object(jwks_response.json())
                claims = _verify_id_token(
                    id_token=id_token,
                    jwks_payload=jwks_payload,
                    expected_client_id=self.client_id,
                    now=self.clock(),
                )
        except (httpx.HTTPError, InvalidSignature, TypeError, ValueError) as error:
            logger.warning(
                "auth.telegram_oauth.verification.failed",
                extra={"error_type": type(error).__name__},
            )
            raise OpenIdConnectOAuthUnavailableError(
                "Telegram OAuth verification failed."
            ) from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
            logger.warning("auth.telegram_oauth.verification.invalid_subject")
            raise OpenIdConnectOAuthUnavailableError(
                "Telegram OAuth returned an invalid user subject."
            )
        logger.info("auth.telegram_oauth.verification.completed")
        return subject


def _verify_id_token(
    *,
    id_token: str,
    jwks_payload: Mapping[str, object],
    expected_client_id: str,
    now: float,
) -> Mapping[str, object]:
    """Verify a Telegram RS256 JWT and its OIDC claims without returning secrets."""
    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValueError("Telegram ID token has an invalid shape.")
    header = _json_object(_decode_json_segment(parts[0]))
    claims = _json_object(_decode_json_segment(parts[1]))
    signature = _decode_segment(parts[2])
    if header.get("alg") != "RS256":
        raise ValueError("Telegram ID token uses an unsupported signing algorithm.")
    key_id = header.get("kid")
    if not isinstance(key_id, str) or not key_id:
        raise ValueError("Telegram ID token does not identify a signing key.")
    public_key = _rsa_public_key_for(jwks_payload, key_id)
    public_key.verify(
        signature,
        f"{parts[0]}.{parts[1]}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    if claims.get("iss") != _TELEGRAM_ISSUER:
        raise ValueError("Telegram ID token issuer is invalid.")
    audience = claims.get("aud")
    if not (
        audience == expected_client_id
        or isinstance(audience, list)
        and expected_client_id in audience
    ):
        raise ValueError("Telegram ID token audience is invalid.")
    expires_at = claims.get("exp")
    if not isinstance(expires_at, (int, float)) or expires_at <= now:
        raise ValueError("Telegram ID token is expired or missing expiry.")
    issued_at = claims.get("iat")
    if isinstance(issued_at, (int, float)) and issued_at > now + _MAX_CLOCK_SKEW_SECONDS:
        raise ValueError("Telegram ID token was issued in the future.")
    return claims


def _rsa_public_key_for(jwks_payload: Mapping[str, object], key_id: str) -> rsa.RSAPublicKey:
    keys = jwks_payload.get("keys")
    if not isinstance(keys, list):
        raise ValueError("Telegram JWKS response has no key set.")
    for key in keys:
        if not isinstance(key, Mapping) or key.get("kid") != key_id or key.get("kty") != "RSA":
            continue
        modulus = key.get("n")
        exponent = key.get("e")
        if not isinstance(modulus, str) or not isinstance(exponent, str):
            break
        return rsa.RSAPublicNumbers(_base64url_int(exponent), _base64url_int(modulus)).public_key()
    raise ValueError("Telegram signing key was not found.")


def _json_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("Telegram OAuth response must be a JSON object.")
    return value


def _decode_json_segment(segment: str) -> object:
    try:
        return json.loads(_decode_segment(segment))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Telegram ID token contains invalid JSON.") from error


def _decode_segment(segment: str) -> bytes:
    if not segment or len(segment) > 16384:
        raise ValueError("Telegram ID token segment is invalid.")
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, binascii.Error) as error:
        raise ValueError("Telegram ID token segment is not base64url.") from error


def _base64url_int(value: str) -> int:
    decoded = _decode_segment(value)
    number = int.from_bytes(decoded, "big")
    if number <= 0:
        raise ValueError("Telegram JWKS integer is invalid.")
    return number
