"""FastAPI routers for /organizations and /users endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUserContext,
    CurrentUserDep,
    DbSession,
    PaginationDep,
    require_roles,
)
from app.modules.users.controller import UserController
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    OrganizationResponse,
    OrganizationUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.modules.users.service import UserService
from app.shared.enums import UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

org_router = APIRouter(prefix="/organizations", tags=["organizations"])
router = APIRouter(prefix="/users", tags=["users"])


def get_controller(db: DbSession) -> UserController:
    return UserController(UserService(UserRepository(db)))


@org_router.get("/current", response_model=APIResponse[OrganizationResponse])
def get_current_organization(
    current_user: CurrentUserDep,
    controller: UserController = Depends(get_controller),
) -> APIResponse[OrganizationResponse]:
    return controller.get_current_organization(current_user)


@org_router.patch("/current", response_model=APIResponse[OrganizationResponse])
def update_current_organization(
    payload: OrganizationUpdate,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: UserController = Depends(get_controller),
) -> APIResponse[OrganizationResponse]:
    return controller.update_current_organization(current_user, payload)


@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users(
    pagination: PaginationDep,
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: UserController = Depends(get_controller),
) -> PaginatedResponse[UserResponse]:
    return controller.list_users(
        current_user,
        pagination,
        role=role,
        is_active=is_active,
        search=search,
    )


@router.post("", response_model=APIResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: UserController = Depends(get_controller),
) -> APIResponse[UserResponse]:
    return controller.create_user(current_user, payload)


@router.patch("/{user_id}", response_model=APIResponse[UserResponse])
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: UserController = Depends(get_controller),
) -> APIResponse[UserResponse]:
    return controller.update_user(current_user, user_id, payload)
