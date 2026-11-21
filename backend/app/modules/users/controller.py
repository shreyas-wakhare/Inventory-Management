"""HTTP controller layer for organizations and users endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
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


class UserController:
    """Coordinates HTTP envelopes for organization and user operations."""

    def __init__(self, service: UserService) -> None:
        self.service = service

    def get_current_organization(self, ctx: CurrentUserContext) -> APIResponse[OrganizationResponse]:
        return APIResponse(data=self.service.get_current_organization(ctx))

    def update_current_organization(
        self,
        ctx: CurrentUserContext,
        payload: OrganizationUpdate,
    ) -> APIResponse[OrganizationResponse]:
        return APIResponse(data=self.service.update_current_organization(ctx, payload))

    def list_users(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[UserResponse]:
        return self.service.list_users(
            ctx,
            pagination,
            role=role,
            is_active=is_active,
            search=search,
        )

    def create_user(
        self,
        ctx: CurrentUserContext,
        payload: UserCreate,
    ) -> APIResponse[UserResponse]:
        return APIResponse(data=self.service.create_user(ctx, payload), message="created")

    def update_user(
        self,
        ctx: CurrentUserContext,
        user_id: UUID,
        payload: UserUpdate,
    ) -> APIResponse[UserResponse]:
        return APIResponse(data=self.service.update_user(ctx, user_id, payload))
