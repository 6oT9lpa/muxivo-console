"""Route connection candidate discovery to a platform-specific adapter."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import PlatformConnectionCandidateCatalogReader
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformConnectionCandidateCatalogRouter:
    """Keep platform dispatch out of the use case and fail closed when unsupported."""

    catalogs: Mapping[Platform, PlatformConnectionCandidateCatalogReader]

    async def list_for_platform(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        platform: Platform,
        correlation_id: UUID,
    ) -> PlatformConnectionCandidateCatalog:
        catalog = self.catalogs.get(platform)
        if catalog is None:
            logger.warning(
                "platform_connection_candidates.catalog.unsupported_platform",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "correlation_id": str(correlation_id),
                },
            )
            raise PlatformControlUnavailableError(
                "No platform connection candidate catalog is available."
            )
        return await catalog.list_for_organization(
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
