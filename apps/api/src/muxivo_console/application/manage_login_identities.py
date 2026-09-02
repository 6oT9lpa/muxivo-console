"""Manage first-party login identities for the authenticated Console user."""

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    IdentifierGenerator,
    LoginIdentityManagementReader,
    LoginIdentityUnlinkWriter,
    UserStatusReader,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProfile, LoginIdentityProvider, UserStatus

logger = logging.getLogger(__name__)


class LoginIdentityManagementRejectedError(PermissionError):
    """Safe failure for denied account identity management operations."""


@dataclass(frozen=True, slots=True)
class ListLoginIdentitiesCommand:
    actor_id: UUID
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class UnlinkLoginIdentityCommand:
    principal: BrowserSessionPrincipal
    identity_id: UUID
    correlation_id: UUID


@dataclass(slots=True)
class ListLoginIdentities:
    user_statuses: UserStatusReader
    identities: LoginIdentityManagementReader

    async def execute(
        self, command: ListLoginIdentitiesCommand
    ) -> tuple[LoginIdentityProfile, ...]:
        logger.info(
            "identity.list.started",
            extra={
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "identity.list.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Access denied.")
        identities = tuple(await self.identities.list_for_user(user_id=command.actor_id))
        logger.info(
            "identity.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "identity_count": len(identities),
                "correlation_id": str(command.correlation_id),
            },
        )
        return identities


@dataclass(slots=True)
class UnlinkLoginIdentity:
    identifiers: IdentifierGenerator
    user_statuses: UserStatusReader
    identities: LoginIdentityManagementReader
    unlinker: LoginIdentityUnlinkWriter
    recent_authentication: RequireRecentAuthentication

    async def execute(self, command: UnlinkLoginIdentityCommand) -> LoginIdentityProfile:
        actor_id = command.principal.user_id
        logger.info(
            "identity.unlink.started",
            extra={
                "actor_id": str(actor_id),
                "identity_id": str(command.identity_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        try:
            self.recent_authentication.check(command.principal)
        except RecentAuthenticationRequiredError:
            logger.warning(
                "identity.unlink.denied_recent_authentication",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise
        if await self.user_statuses.get_status(user_id=actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "identity.unlink.denied_inactive_user",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Identity unlink denied.")
        identities = tuple(await self.identities.list_for_user(user_id=actor_id))
        target = next(
            (identity for identity in identities if identity.id == command.identity_id),
            None,
        )
        if target is None:
            logger.warning(
                "identity.unlink.not_found",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Identity unlink denied.")
        if target.provider is LoginIdentityProvider.EMAIL:
            logger.warning(
                "identity.unlink.denied_email_identity",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Email identity cannot be unlinked.")
        if len(identities) <= 1:
            logger.warning(
                "identity.unlink.denied_last_usable_identity",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Last usable identity cannot be removed.")

        unlinked = await self.unlinker.unlink(
            identity_id=target.id,
            user_id=actor_id,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=actor_id,
                organization_id=None,
                action="identity.unlink",
                resource_type="login_identity",
                resource_id=str(target.id),
                result="succeeded",
            ),
        )
        if not unlinked:
            logger.warning(
                "identity.unlink.conflict",
                extra={
                    "actor_id": str(actor_id),
                    "identity_id": str(command.identity_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise LoginIdentityManagementRejectedError("Identity unlink failed.")
        logger.info(
            "identity.unlink.completed",
            extra={
                "actor_id": str(actor_id),
                "identity_id": str(command.identity_id),
                "provider": target.provider.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        return target
