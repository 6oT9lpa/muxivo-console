"""Authenticate an active first-party user without e-mail enumeration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.authenticate_email_password_command import (
    AuthenticateEmailPasswordCommand,
)
from muxivo_console.application.authentication_rejected_error import (
    AuthenticationRejectedError,
)
from muxivo_console.application.create_browser_session import (
    CreateBrowserSessionCommand,
    IssuedBrowserSession,
)
from muxivo_console.application.create_browser_session_use_case import CreateBrowserSession
from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailLookupHasher,
    EmailPasswordAccountReader,
    PasswordHasher,
)
from muxivo_console.application.session_creation_error import SessionCreationRejectedError
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel

logger = logging.getLogger("muxivo_console.application.authenticate_email_password")


@dataclass(slots=True)
class AuthenticateEmailPassword:
    """Authenticate a first-party account and issue an opaque browser session."""

    email_normalizer: EmailAddressNormalizer
    email_lookup_hasher: EmailLookupHasher
    accounts: EmailPasswordAccountReader
    password_hasher: PasswordHasher
    session_creator: CreateBrowserSession

    async def execute(self, command: AuthenticateEmailPasswordCommand) -> IssuedBrowserSession:
        logger.info(
            "auth.email_password.authenticate.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        try:
            normalized_email = self.email_normalizer.normalize(command.email)
        except ValueError as error:
            self.password_hasher.hash(command.password)
            logger.warning(
                "auth.email_password.authenticate.rejected_email",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise AuthenticationRejectedError("Authentication could not be completed.") from error

        account = await self.accounts.find_by_email_lookup_hash(
            email_lookup_hash=self.email_lookup_hasher.lookup_hash(normalized_email)
        )
        if account is None:
            self.password_hasher.hash(command.password)
            logger.warning(
                "auth.email_password.authenticate.rejected_account",
                extra={"correlation_id": str(command.correlation_id)},
            )
            raise AuthenticationRejectedError("Authentication could not be completed.")

        password_matches = self.password_hasher.verify(account.password_hash, command.password)
        if not password_matches or account.status is not UserStatus.ACTIVE:
            logger.warning(
                "auth.email_password.authenticate.rejected_credentials",
                extra={
                    "user_id": str(account.user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise AuthenticationRejectedError("Authentication could not be completed.")
        try:
            issued = await self.session_creator.execute(
                CreateBrowserSessionCommand(
                    user_id=account.user_id,
                    correlation_id=command.correlation_id,
                    assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
                    client_ip=command.client_ip,
                    user_agent=command.user_agent,
                )
            )
        except SessionCreationRejectedError as error:
            logger.warning(
                "auth.email_password.authenticate.session_rejected",
                extra={
                    "user_id": str(account.user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise AuthenticationRejectedError("Authentication could not be completed.") from error
        logger.info(
            "auth.email_password.authenticate.completed",
            extra={
                "user_id": str(account.user_id),
                "session_id": str(issued.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return issued
