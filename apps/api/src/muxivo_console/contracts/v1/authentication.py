"""Versioned public contracts for first-party Console authentication."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr


class EmailPasswordRegistrationRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=1024)
    display_name: str = Field(min_length=1, max_length=64)


class EmailPasswordRegistrationResponse(BaseModel):
    """Enumeration-safe result for both accepted and duplicate registrations."""

    status: Literal["accepted"] = "accepted"


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
