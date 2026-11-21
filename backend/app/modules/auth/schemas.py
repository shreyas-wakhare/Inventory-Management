"""Pydantic v2 request/response schemas for authentication and session identity."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    organization_code: str | None = Field(default=None, max_length=32)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    organization_id: UUID
    organization_code: str
    email: str
    full_name: str
    role: UserRole


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserResponse
