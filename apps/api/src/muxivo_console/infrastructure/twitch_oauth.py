"""Twitch OAuth authorization-code adapter for verified Console identity linking."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx


class TwitchOAuthUnavailableError(RuntimeError):
    """Raised when Twitch OAuth cannot safely resolve a provider subject."""


@dataclass(frozen=True, slots=True)
class TwitchOAuthClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    api_base_url: str = "https://api.twitch.tv/helix"
    token_url: str = "https://id.twitch.tv/oauth2/token"
    authorize_url: str = "https://id.twitch.tv/oauth2/authorize"
    timeout: float = 10.0
    transport: httpx.AsyncBaseTransport | None = None

    def __post_init__(self) -> None:
        if (
            not self.client_id
            or not self.client_secret
            or not self.redirect_uri.startswith("https://")
        ):
            raise ValueError("Twitch OAuth credentials and HTTPS redirect URI are required.")

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "user:read:email",
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
                    raise ValueError("Twitch token response did not contain an access token.")
                user_response = await client.get(
                    f"{self.api_base_url}/users",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Client-Id": self.client_id,
                    },
                )
                user_response.raise_for_status()
                user_payload = user_response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TwitchOAuthUnavailableError("Twitch OAuth verification failed.") from error
        subject = _first_twitch_user_subject(user_payload)
        if subject is None:
            raise TwitchOAuthUnavailableError("Twitch OAuth returned an invalid user subject.")
        return subject


def _first_twitch_user_subject(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    users = payload.get("data")
    if not isinstance(users, list) or not users:
        return None
    first = users[0]
    if not isinstance(first, dict):
        return None
    subject = first.get("id")
    if not isinstance(subject, str) or not subject.isdigit() or len(subject) > 255:
        return None
    return subject
