"""Base generic repository class encapsulating tenant-scoped SQLAlchemy 2.0 data access."""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Abstract base repository for domain data-access layers."""

    model: type[ModelT] | None = None

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_org(
        self,
        model_cls: type[ModelT],
        record_id: UUID,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> ModelT | None:
        """Fetch a single tenant-owned entity by primary key and organization_id."""
        stmt = select(model_cls).where(
            model_cls.id == record_id,  # type: ignore[attr-defined]
            model_cls.organization_id == organization_id,  # type: ignore[attr-defined]
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def count_query(self, stmt: Select[Any]) -> int:
        """Count total rows for a SELECT statement via subquery."""
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        return int(self.db.scalar(count_stmt) or 0)
