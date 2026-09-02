"""List browser-safe platform resources for the connection wizard."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.access_denied_error import AccessDeniedError
from muxivo_console.application.list_platform_connection_candidates_command import (
    ListPlatformConnectionCandidatesCommand,
)
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionCandidateReader,
)
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)

logger = logging.getLogger("muxivo_console.application.list_platform_connection_candidates")


@dataclass(slots=True)
class ListPlatformConnectionCandidates:
    """Authorize resource management before discovering owned platform resources."""

    authorizer: OrganizationAuthorizer
    candidates: PlatformConnectionCandidateReader

    async def execute(
        self, command: ListPlatformConnectionCandidatesCommand
    ) -> PlatformConnectionCandidateCatalog:
        logger.info(
            "platform_connection_candidates.list.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "platform": command.platform.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                resource=AuthorizationResource.PLATFORM_CONNECTIONS,
                action=AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            logger.warning(
                "platform_connection_candidates.list.denied_rbac",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise AccessDeniedError("The actor is not allowed to discover platform resources.")

        catalog = await self.candidates.list_for_platform(
            organization_id=command.organization_id,
            actor_id=command.actor_id,
            platform=command.platform,
            correlation_id=command.correlation_id,
        )
        logger.info(
            "platform_connection_candidates.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "platform": command.platform.value,
                "candidate_count": len(catalog.items),
                "identity_linked": catalog.identity_linked,
                "correlation_id": str(command.correlation_id),
            },
        )
        return catalog
