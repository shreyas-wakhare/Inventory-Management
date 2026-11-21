"""Business logic service for JWT authentication and session identity."""

from __future__ import annotations

from uuid import UUID

from app.core.config import settings
from app.core.dependencies import CurrentUserContext
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.shared.enums import UserRole


class AuthService:
    """Issues and refreshes JWT tokens and resolves active session identity."""

    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository

    def login(self, payload: LoginRequest) -> TokenPairResponse:
        if not (settings.APP_ENV == "development" and settings.DEV_AUTH_BYPASS):
            raise UnauthorizedError(
                "Password credential verification requires Phase B auth schema hardening."
            )

        result = self.repository.get_active_user_by_email(
            payload.email,
            organization_code=payload.organization_code,
        )
        if result is None:
            raise UnauthorizedError("Invalid credentials or inactive account.")

        user, org = result
        access_token, expires_in = create_access_token(
            user_id=user.id,
            organization_id=org.id,
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            organization_id=org.id,
            role=user.role,
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=CurrentUserResponse(
                user_id=user.id,
                organization_id=org.id,
                organization_code=org.code,
                email=user.email,
                full_name=user.full_name,
                role=UserRole(user.role),
            ),
        )

    def refresh(self, payload: RefreshTokenRequest) -> TokenPairResponse:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
        result = self.repository.get_active_user_by_id(
            UUID(claims["sub"]),
            UUID(claims["org_id"]),
        )
        if result is None:
            raise UnauthorizedError("User or organization is no longer active.")

        user, org = result
        access_token, expires_in = create_access_token(
            user_id=user.id,
            organization_id=org.id,
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            organization_id=org.id,
            role=user.role,
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=CurrentUserResponse(
                user_id=user.id,
                organization_id=org.id,
                organization_code=org.code,
                email=user.email,
                full_name=user.full_name,
                role=UserRole(user.role),
            ),
        )

    def get_me(self, current_user: CurrentUserContext) -> CurrentUserResponse:
        return CurrentUserResponse(
            user_id=current_user.user_id,
            organization_id=current_user.organization_id,
            organization_code=current_user.organization_code,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
        )
