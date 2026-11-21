"""Data-access repository for read-only stock_movements audit ledger queries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.stock_movements.models import StockMovement
from app.modules.users.models import User
from app.shared.enums import MovementType, OwnershipSource
from app.shared.repository import BaseRepository


class StockMovementRepository(BaseRepository[StockMovement]):
    """Encapsulates tenant-scoped read queries over the append-only audit ledger."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_movements(
        self,
        organization_id: UUID,
        *,
        item_id: UUID | None = None,
        equipment_unit_id: UUID | None = None,
        project_id: UUID | None = None,
        ownership_source: OwnershipSource | None = None,
        movement_type: MovementType | None = None,
        reference_number: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[StockMovement, Item, EquipmentUnit | None, Project | None, User]], int]:
        stmt = (
            select(StockMovement, Item, EquipmentUnit, Project, User)
            .join(Item, StockMovement.item_id == Item.id)
            .join(User, StockMovement.created_by == User.id)
            .outerjoin(EquipmentUnit, StockMovement.equipment_unit_id == EquipmentUnit.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .where(StockMovement.organization_id == organization_id)
        )
        if item_id is not None:
            stmt = stmt.where(StockMovement.item_id == item_id)
        if equipment_unit_id is not None:
            stmt = stmt.where(StockMovement.equipment_unit_id == equipment_unit_id)
        if project_id is not None:
            stmt = stmt.where(StockMovement.project_id == project_id)
        if ownership_source is not None:
            stmt = stmt.where(StockMovement.ownership_source == ownership_source.value)
        if movement_type is not None:
            stmt = stmt.where(StockMovement.movement_type == movement_type.value)
        if reference_number and reference_number.strip():
            stmt = stmt.where(
                StockMovement.reference_number.ilike(f"%{reference_number.strip()}%")
            )
        if date_from is not None:
            stmt = stmt.where(
                StockMovement.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
            )
        if date_to is not None:
            stmt = stmt.where(
                StockMovement.created_at <= datetime.combine(date_to, time.max, tzinfo=UTC)
            )

        total = self.count_query(stmt)
        rows = [
            (r[0], r[1], r[2], r[3], r[4])
            for r in self.db.execute(
                stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total
