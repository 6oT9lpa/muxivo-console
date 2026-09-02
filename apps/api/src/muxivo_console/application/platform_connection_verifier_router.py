"""Platform-dispatching adapter for ownership verification."""

import logging
from collections.abc import Mapping
from uuid import UUID

from muxivo_console.application.ports import PlatformConnectionVerifier
from muxivo_console.domain.activity import Platform

logger = logging.getLogger("muxivo_console.application.register_platform_connection")


class PlatformConnectionVerifierRouter:
    """Dispatch ownership verification to the adapter for the requested platform."""

    def __init__(self, verifiers: Mapping[Platform, PlatformConnectionVerifier]) -> None:
        self._verifiers = verifiers

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        verifier = self._verifiers.get(platform)
        if verifier is None:
            logger.warning(
                "platform_connection.verify.unsupported_platform",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(correlation_id),
                },
            )
            return False
        return await verifier.verify_registration(
            actor_id=actor_id,
            organization_id=organization_id,
            platform=platform,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )
