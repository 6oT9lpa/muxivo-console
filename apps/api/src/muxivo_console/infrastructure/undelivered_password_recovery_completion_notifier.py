"""Safe no-op adapter for unavailable password-change notifications."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class UndeliveredPasswordRecoveryCompletionNotifier:
    """Record missing delivery configuration without exposing account data."""

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        changed_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.warning(
            "password.recovery.completion_notification.unconfigured",
            extra={
                "user_id": str(user_id),
                "changed_at": changed_at.isoformat(),
                "correlation_id": str(correlation_id),
            },
        )
