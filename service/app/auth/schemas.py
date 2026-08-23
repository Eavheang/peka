from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


Role = Literal["admin", "senior", "staff"]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or any(not part for part in value.split("@")):
            raise ValueError("invalid email")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserCreate(LoginRequest):
    password: str = Field(min_length=12, max_length=1024)
    role: Role = "staff"


class UserActivationUpdate(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: Role
    is_active: bool
