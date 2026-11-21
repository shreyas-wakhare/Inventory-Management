"""Shared FastAPI dependencies: DB session, pagination, auth/tenant context, and RBAC."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import InsufficientRoleError, UnauthorizedError
from app.core.security import decode_token
from app.modules.users.models import Organization, User
from app.shared.enums import UserRole
from database.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


class PaginationParams(BaseModel):
    """Standard pagination parameters capped at 100 rows per SDD-2."""

    page: int = 1
    page_size: int = 25

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page (max 100)"),
) -> PaginationParams:
    """Resolve and validate pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]


class CurrentUserContext(BaseModel):
    """Verified authenticated user and tenant context resolved per request."""

    user_id: UUID
    organization_id: UUID
    organization_code: str
    email: str
    full_name: str
    role: UserRole


def _load_active_user_context(
    db: Session,
    *,
    user_id: UUID | None = None,
    email: str | None = None,
    organization_id: UUID | None = None,
) -> CurrentUserContext:
    stmt = (
        select(User, Organization)
        .join(Organization, User.organization_id == Organization.id)
        .where(User.is_active.is_(True), Organization.is_active.is_(True))
    )
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    if organization_id is not None:
        stmt = stmt.where(User.organization_id == organization_id)
    if email is not None:
        stmt = stmt.where(User.email == email.strip().lower())

    row = db.execute(stmt).first()
    if row is None:
        raise UnauthorizedError("Authenticated user or organization is inactive or does not exist.")

    user, org = row
    return CurrentUserContext(
        user_id=user.id,
        organization_id=org.id,
        organization_code=org.code,
        email=user.email,
        full_name=user.full_name,
        role=UserRole(user.role),
    )


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    dev_user_email: Annotated[
        str | None,
        Header(
            alias="X-Dev-User-Email",
            description="Local development only: impersonate an active seeded user when DEV_AUTH_BYPASS=true.",
        ),
    ] = None,
) -> CurrentUserContext:
    """Resolve CurrentUserContext from JWT Bearer token or gated local dev bootstrap."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise UnauthorizedError("Invalid Authorization header; expected 'Bearer <token>'.")
        payload = decode_token(token.strip(), expected_type="access")
        return _load_active_user_context(
            db,
            user_id=UUID(payload["sub"]),
            organization_id=UUID(payload["org_id"]),
        )

    # Local dev / Swagger bootstrap mode (strictly blocked outside APP_ENV == "development")
    if settings.APP_ENV == "development" and settings.DEV_AUTH_BYPASS:
        target_email = (dev_user_email or settings.DEV_DEFAULT_USER_EMAIL).strip().lower()
        return _load_active_user_context(db, email=target_email)

    raise UnauthorizedError("Missing Bearer authentication token.")


CurrentUserDep = Annotated[CurrentUserContext, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole | str) -> Callable[[CurrentUserContext], CurrentUserContext]:
    """Build a FastAPI dependency enforcing SDD-2 RBAC permissions."""
    normalized = {UserRole(r) for r in allowed_roles}

    def _role_guard(current_user: CurrentUserDep) -> CurrentUserContext:
        if current_user.role not in normalized:
            raise InsufficientRoleError(
                f"Role '{current_user.role.value}' is not authorized for this endpoint.",
                details={
                    "required_roles": sorted(r.value for r in normalized),
                    "current_role": current_user.role.value,
                },
            )
        return current_user

    return _role_guard
