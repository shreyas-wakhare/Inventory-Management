"""FastAPI router definitions for authentication endpoints."""

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserDep, DbSession
from app.modules.auth.controller import AuthController
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.modules.auth.service import AuthService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def get_controller(db: DbSession) -> AuthController:
    return AuthController(AuthService(AuthRepository(db)))


@router.post("/login", response_model=APIResponse[TokenPairResponse])
def login(
    payload: LoginRequest,
    controller: AuthController = Depends(get_controller),
) -> APIResponse[TokenPairResponse]:
    return controller.login(payload)


@router.post("/refresh", response_model=APIResponse[TokenPairResponse])
def refresh_token(
    payload: RefreshTokenRequest,
    controller: AuthController = Depends(get_controller),
) -> APIResponse[TokenPairResponse]:
    return controller.refresh(payload)


@router.get("/me", response_model=APIResponse[CurrentUserResponse])
def get_me(
    current_user: CurrentUserDep,
    controller: AuthController = Depends(get_controller),
) -> APIResponse[CurrentUserResponse]:
    return controller.get_me(current_user)
