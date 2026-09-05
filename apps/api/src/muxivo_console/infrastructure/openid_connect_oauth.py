"""Generic server-side PKCE adapter for providers exposing OIDC-style user info."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from muxivo_console.infrastructure.openid_connect_oauth_unavailable_error import (
    OpenIdConnectOAuthUnavailableError,
)


@dataclass(frozen=True, slots=True)
class OpenIdConnectOAuthClient:
    """Exchange an authorization code and return only the verified subject."""

    provider_label: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: tuple[str, ...]
    subject_field: str = "sub"
    timeout: float = 10.0
    transport: httpx.AsyncBaseTransport | None = None

    def __post_init__(self) -> None:
        if (
            not self.provider_label.strip()
            or not self.client_id
            or not self.client_secret
            or not self.redirect_uri.startswith("https://")
            or not self.authorize_url.startswith("https://")
            or not self.token_url.startswith("https://")
            or not self.userinfo_url.startswith("https://")
            or not self.scopes
            or not self.subject_field.strip()
        ):
            raise ValueError("OIDC OAuth credentials, HTTPS endpoints and scopes are required.")

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.authorize_url}?{query}"

    async def resolve_subject(self, *, authorization_code: str, code_verifier: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                token_response = await client.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self.redirect_uri,
                        "code_verifier": code_verifier,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                token_response.raise_for_status()
                token_payload = token_response.json()
                access_token = (
                    token_payload.get("access_token") if isinstance(token_payload, dict) else None
                )
                if not isinstance(access_token, str) or not access_token:
                    raise ValueError("OIDC token response did not contain an access token.")
                user_response = await client.get(
                    self.userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_response.raise_for_status()
                user_payload = user_response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OpenIdConnectOAuthUnavailableError(
                f"{self.provider_label} OAuth verification failed."
            ) from error

        subject = user_payload.get(self.subject_field) if isinstance(user_payload, dict) else None
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
            raise OpenIdConnectOAuthUnavailableError(
                f"{self.provider_label} OAuth returned an invalid user subject."
            )
        return subject
