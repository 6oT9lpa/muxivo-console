"""Safe development fallback for password recovery delivery."""

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class UndeliveredPasswordRecoveryNotifier:
    """Never pretends that a recovery message was delivered."""

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        raw_token: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.warning(
            "password.recovery.delivery.unconfigured",
            extra={
                "user_id": str(user_id),
                "expires_at": expires_at.isoformat(),
                "correlation_id": str(correlation_id),
                "token_length": len(raw_token),
            },
        )
