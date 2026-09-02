"""List platform Control API modules after organization authorization."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.access_denied_error import AccessDeniedError
from muxivo_console.application.ports import ModuleCatalog, OrganizationAuthorizer
from muxivo_console.domain.activity import ControlModule
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)

logger = logging.getLogger("muxivo_console.application.list_control_modules")


@dataclass(slots=True)
class ListControlModules:
    """List only the modules permitted for the authenticated organization actor."""

    authorizer: OrganizationAuthorizer
    catalog: ModuleCatalog

    async def execute(
        self, *, actor_id: UUID, organization_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]:
        logger.info(
            "platform.control_modules.list.started",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "correlation_id": str(correlation_id),
            },
        )
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            logger.warning(
                "platform.control_modules.list.denied_rbac",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "correlation_id": str(correlation_id),
                },
            )
            raise AccessDeniedError("The actor is not allowed to view this organization.")
        modules = await self.catalog.list_for_organization(
            actor_id=actor_id, organization_id=organization_id, correlation_id=correlation_id
        )
        logger.info(
            "platform.control_modules.list.completed",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "module_count": len(modules),
                "correlation_id": str(correlation_id),
            },
        )
        return modules
