"""Twitch Control API adapter for browser-safe connection candidate discovery."""

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import LoginIdentityReader
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.platform_connection_candidate import PlatformConnectionCandidate
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TwitchPlatformConnectionCandidateCatalog:
    """Ask Twitch for channels the linked identity owns or administers."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    identities: LoginIdentityReader
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_base_url(self.base_url, self.allow_insecure_http)

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformConnectionCandidateCatalog:
        logger.info(
            "platform_connection_candidates.twitch.started",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "correlation_id": str(correlation_id),
            },
        )
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.TWITCH
        )
        if platform_subject is None:
            logger.info(
                "platform_connection_candidates.twitch.identity_missing",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "correlation_id": str(correlation_id),
                },
            )
            return PlatformConnectionCandidateCatalog(
                platform=Platform.TWITCH,
                items=(),
                identity_linked=False,
            )

        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.PLATFORM_CONNECTIONS,
            action=AuthorizationAction.MANAGE,
            correlation_id=correlation_id,
            platform_subject=platform_subject,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connection-candidates",
                    params={"platform": Platform.TWITCH.value},
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            logger.warning(
                "platform_connection_candidates.twitch.unavailable",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "correlation_id": str(correlation_id),
                },
            )
            raise PlatformControlUnavailableError(
                "Twitch Control API connection candidate discovery failed."
            ) from error
        catalog = _parse_catalog(payload)
        logger.info(
            "platform_connection_candidates.twitch.completed",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "candidate_count": len(catalog.items),
                "correlation_id": str(correlation_id),
            },
        )
        return catalog


def _parse_catalog(payload: Any) -> PlatformConnectionCandidateCatalog:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise PlatformControlUnavailableError(
            "Twitch Control API returned an invalid connection candidate payload."
        )
    try:
        items_to_parse = payload["items"]
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("external_resource_id"), str)
            or not isinstance(item.get("display_name"), str)
            for item in items_to_parse
        ):
            raise ValueError("Connection candidate fields must be strings.")
        items = tuple(
            PlatformConnectionCandidate(
                platform=Platform.TWITCH,
                external_resource_id=item["external_resource_id"],
                display_name=item["display_name"],
            )
            for item in items_to_parse
        )
        return PlatformConnectionCandidateCatalog(
            platform=Platform.TWITCH,
            items=items,
            identity_linked=True,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Twitch Control API returned invalid connection candidate values."
        ) from error


def _validate_base_url(base_url: str, allow_insecure_http: bool) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Twitch Control API base URL must be an absolute service URL.")
    if parsed.scheme == "http" and not allow_insecure_http:
        raise ValueError("Twitch Control API base URL must use HTTPS outside development.")
