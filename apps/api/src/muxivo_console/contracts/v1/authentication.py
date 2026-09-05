"""Versioned public contracts for first-party Console authentication."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr


class EmailPasswordRegistrationRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=1024)
    display_name: str = Field(min_length=1, max_length=64)


class EmailPasswordRegistrationResponse(BaseModel):
    """Enumeration-safe response for the pending e-mail verification flow."""

    status: Literal["verification_required"] = "verification_required"
    verification_token: str | None = None


class EmailPasswordRegistrationVerificationRequest(BaseModel):
    """Bearer token plus the six-digit code delivered to the e-mail inbox."""

    token: SecretStr = Field(min_length=1, max_length=4096)
    code: str = Field(pattern=r"^\d{6}$")


class EmailPasswordRegistrationVerificationResponse(BaseModel):
    status: Literal["verified"] = "verified"


class EmailPasswordRegistrationVerificationResendRequest(BaseModel):
    """Request a fresh code without exposing whether the pending flow exists."""

    token: SecretStr = Field(min_length=1, max_length=4096)


class EmailPasswordLoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)


class BrowserSessionReauthenticationRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=12, max_length=1024)


class PasswordRecoveryRequest(BaseModel):
    email: EmailStr


class PasswordRecoveryRequestResponse(BaseModel):
    status: Literal["accepted"] = "accepted"


class PasswordRecoveryCompletionRequest(BaseModel):
    token: SecretStr = Field(min_length=1, max_length=4096)
    new_password: SecretStr = Field(min_length=12, max_length=1024)


class OAuthProviderCatalogResponse(BaseModel):
    """Browser-safe list of OAuth providers configured for Console login."""

    providers: list[Literal["discord", "twitch", "telegram", "google", "yandex"]] = Field(
        default_factory=list
    )
