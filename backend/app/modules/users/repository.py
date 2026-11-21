"""Data-access repository for organizations and users."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.users.models import Organization, User
from app.shared.enums import UserRole
from app.shared.repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Encapsulates tenant-scoped SQLAlchemy queries for organizations and users."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_organization(self, organization_id: UUID) -> Organization | None:
        return self.db.scalar(select(Organization).where(Organization.id == organization_id))

    def list_users(
        self,
        organization_id: UUID,
        *,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.organization_id == organization_id)
        if role is not None:
            stmt = stmt.where(User.role == role.value)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

        total = self.count_query(stmt)
        rows = list(
            self.db.scalars(
                stmt.order_by(User.full_name.asc(), User.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return rows, total

    def get_user_by_email(self, organization_id: UUID, email: str) -> User | None:
        return self.db.scalar(
            select(User).where(
                User.organization_id == organization_id,
                User.email == email.strip().lower(),
            )
        )

    def get_user_by_id(self, organization_id: UUID, user_id: UUID) -> User | None:
        return self.get_by_id_for_org(User, user_id, organization_id)
