"""HTTP controller layer for authentication endpoints."""

from app.core.dependencies import CurrentUserContext
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.modules.auth.service import AuthService
from app.shared.schemas import APIResponse


class AuthController:
    """Coordinates HTTP request/response adaptation for auth routes."""

    def __init__(self, service: AuthService) -> None:
        self.service = service

    def login(self, payload: LoginRequest) -> APIResponse[TokenPairResponse]:
        return APIResponse(data=self.service.login(payload))

    def refresh(self, payload: RefreshTokenRequest) -> APIResponse[TokenPairResponse]:
        return APIResponse(data=self.service.refresh(payload))

    def get_me(self, current_user: CurrentUserContext) -> APIResponse[CurrentUserResponse]:
        return APIResponse(data=self.service.get_me(current_user))
