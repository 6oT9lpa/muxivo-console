"""Authenticate an active first-party user without e-mail account enumeration."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.create_browser_session import (
    CreateBrowserSession,
    CreateBrowserSessionCommand,
    IssuedBrowserSession,
    SessionCreationRejectedError,
)
from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailLookupHasher,
    EmailPasswordAccountReader,
    PasswordHasher,
)
from muxivo_console.domain.identity import UserStatus


class AuthenticationRejectedError(PermissionError):
    """Publicly safe failure that never reveals whether a password account exists."""


@dataclass(frozen=True, slots=True)
class AuthenticateEmailPasswordCommand:
    email: str
    password: str
    correlation_id: UUID


@dataclass(slots=True)
class AuthenticateEmailPassword:
    email_normalizer: EmailAddressNormalizer
    email_lookup_hasher: EmailLookupHasher
    accounts: EmailPasswordAccountReader
    password_hasher: PasswordHasher
    session_creator: CreateBrowserSession

    async def execute(self, command: AuthenticateEmailPasswordCommand) -> IssuedBrowserSession:
        try:
            normalized_email = self.email_normalizer.normalize(command.email)
        except ValueError as error:
            self.password_hasher.hash(command.password)
            raise AuthenticationRejectedError("Authentication could not be completed.") from error
        account = await self.accounts.find_by_email_lookup_hash(
            email_lookup_hash=self.email_lookup_hasher.lookup_hash(normalized_email)
        )
        if account is None:
            self.password_hasher.hash(command.password)
            raise AuthenticationRejectedError("Authentication could not be completed.")
        password_matches = self.password_hasher.verify(account.password_hash, command.password)
        if not password_matches or account.status is not UserStatus.ACTIVE:
            raise AuthenticationRejectedError("Authentication could not be completed.")
        try:
            return await self.session_creator.execute(
                CreateBrowserSessionCommand(
                    user_id=account.user_id,
                    correlation_id=command.correlation_id,
                )
            )
        except SessionCreationRejectedError as error:
            raise AuthenticationRejectedError("Authentication could not be completed.") from error
