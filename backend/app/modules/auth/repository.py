"""Data-access repository for authentication user/organization lookups."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import Organization, User
from app.shared.repository import BaseRepository


class AuthRepository(BaseRepository[User]):
    """Encapsulates active user + organization lookups for auth flows."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_active_user_by_email(
        self,
        email: str,
        *,
        organization_code: str | None = None,
    ) -> tuple[User, Organization] | None:
        stmt = (
            select(User, Organization)
            .join(Organization, User.organization_id == Organization.id)
            .where(
                User.email == email.strip().lower(),
                User.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        )
        if organization_code:
            stmt = stmt.where(Organization.code == organization_code.strip().upper())
        row = self.db.execute(stmt).first()
        return (row[0], row[1]) if row else None

    def get_active_user_by_id(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> tuple[User, Organization] | None:
        stmt = (
            select(User, Organization)
            .join(Organization, User.organization_id == Organization.id)
            .where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        )
        row = self.db.execute(stmt).first()
        return (row[0], row[1]) if row else None
