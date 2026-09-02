"""Safe development fallback for organization invitation delivery."""

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class UndeliveredOrganizationInvitationNotifier:
    """Never pretends that an invitation was delivered."""

    async def send(
        self,
        *,
        invitation_id: UUID,
        organization_name: str,
        recipient_email: str,
        role: str,
        raw_token: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> bool:
        logger.warning(
            "organization.invitation.delivery.unconfigured",
            extra={
                "invitation_id": str(invitation_id),
                "organization_name_length": len(organization_name),
                "recipient_domain": _recipient_domain(recipient_email),
                "role": role,
                "expires_at": expires_at.isoformat(),
                "token_length": len(raw_token),
                "correlation_id": str(correlation_id),
            },
        )
        return False


def _recipient_domain(recipient_email: str) -> str:
    _, separator, domain = recipient_email.rpartition("@")
    return domain if separator else "unknown"
