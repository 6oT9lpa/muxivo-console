"""Use case for listing first-party login identities."""

import logging
from dataclasses import dataclass

from muxivo_console.application.list_login_identities_command import ListLoginIdentitiesCommand
from muxivo_console.application.login_identity_management_error import (
    LoginIdentityManagementRejectedError,
)
from muxivo_console.application.ports import LoginIdentityManagementReader, UserStatusReader
from muxivo_console.domain.identity import LoginIdentityProfile, UserStatus

logger = logging.getLogger("muxivo_console.application.manage_login_identities")


@dataclass(slots=True)
class ListLoginIdentities:
    """List the active user's identities without exposing provider credentials."""

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
