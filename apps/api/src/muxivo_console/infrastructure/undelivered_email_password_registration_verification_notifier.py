"""Safe development fallback for registration verification delivery."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class UndeliveredEmailPasswordRegistrationVerificationNotifier:
    """Never pretends that a verification code reached an inbox."""

    async def send(
        self,
        *,
        registration_id: UUID,
        recipient_email: str,
        verification_code: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.warning(
            "auth.email_password.verification_delivery.unconfigured",
            extra={
                "registration_id": str(registration_id),
                "correlation_id": str(correlation_id),
                "expires_at": expires_at.isoformat(),
                "code_length": len(verification_code),
            },
        )
        raise ConnectionError("Registration verification delivery is not configured.")
