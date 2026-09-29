from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


Role = Literal["admin", "senior", "staff"]


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if value.count("@") != 1 or any(not part for part in value.split("@")):
        raise ValueError("invalid email")
    return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserActivationUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: Role


class UserProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Role = "staff"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class InvitationToken(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class InvitationAccept(InvitationToken):
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class InvitationSummary(BaseModel):
    id: UUID
    email: str
    role: Role
    expires_at: datetime
    created_at: datetime


class InvitationResponse(InvitationSummary):
    invite_url: str
    email_sent: bool


class InvitationPreview(BaseModel):
    email: str
    role: Role


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str = ""
    role: Role
    is_active: bool
