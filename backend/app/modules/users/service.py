"""Business logic service for organizations and users."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import DuplicateBusinessKeyError, NotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    OrganizationResponse,
    OrganizationUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.shared.enums import UserRole
from app.shared.schemas import PaginatedResponse, build_pagination_meta


class UserService:
    """Manages tenant organization profile and organization-scoped user accounts."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def get_current_organization(self, ctx: CurrentUserContext) -> OrganizationResponse:
        org = self.repository.get_organization(ctx.organization_id)
        if org is None:
            raise NotFoundError("Organization not found.")
        return OrganizationResponse.model_validate(org)

    def update_current_organization(
        self,
        ctx: CurrentUserContext,
        payload: OrganizationUpdate,
    ) -> OrganizationResponse:
        org = self.repository.get_organization(ctx.organization_id)
        if org is None:
            raise NotFoundError("Organization not found.")
        org.name = payload.name.strip()
        self.repository.db.commit()
        self.repository.db.refresh(org)
        return OrganizationResponse.model_validate(org)

    def list_users(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[UserResponse]:
        rows, total = self.repository.list_users(
            ctx.organization_id,
            role=role,
            is_active=is_active,
            search=search,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse(
            items=[UserResponse.model_validate(u) for u in rows],
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def create_user(self, ctx: CurrentUserContext, payload: UserCreate) -> UserResponse:
        email = payload.email.strip().lower()
        if self.repository.get_user_by_email(ctx.organization_id, email) is not None:
            raise DuplicateBusinessKeyError(
                f"A user with email '{email}' already exists in this organization.",
                details={"email": email},
            )
        user = User(
            organization_id=ctx.organization_id,
            full_name=payload.full_name.strip(),
            email=email,
            role=payload.role.value,
            is_active=True,
        )
        self.repository.db.add(user)
        self.repository.db.commit()
        self.repository.db.refresh(user)
        return UserResponse.model_validate(user)

    def update_user(
        self,
        ctx: CurrentUserContext,
        user_id: UUID,
        payload: UserUpdate,
    ) -> UserResponse:
        user = self.repository.get_user_by_id(ctx.organization_id, user_id)
        if user is None:
            raise NotFoundError("User not found.", details={"user_id": str(user_id)})
        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.role is not None:
            user.role = payload.role.value
        if payload.is_active is not None:
            user.is_active = payload.is_active
        self.repository.db.commit()
        self.repository.db.refresh(user)
        return UserResponse.model_validate(user)
