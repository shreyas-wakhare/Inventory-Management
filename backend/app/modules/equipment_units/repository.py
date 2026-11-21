"""Data-access repository for serialized equipment units."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_movements.models import StockMovement
from app.modules.users.models import User
from app.shared.enums import ConditionStatus, EquipmentUnitStatus
from app.shared.repository import BaseRepository


class EquipmentUnitRepository(BaseRepository[EquipmentUnit]):
    """Encapsulates tenant-scoped queries for serialized equipment units."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(
        self,
        organization_id: UUID,
        unit_id: UUID,
        *,
        for_update: bool = False,
    ) -> EquipmentUnit | None:
        return self.get_by_id_for_org(
            EquipmentUnit,
            unit_id,
            organization_id,
            for_update=for_update,
        )

    def get_by_serial(self, organization_id: UUID, serial_number: str) -> EquipmentUnit | None:
        return self.db.scalar(
            select(EquipmentUnit).where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.serial_number == serial_number.strip(),
            )
        )

    def get_unit_joined(
        self,
        organization_id: UUID,
        unit_id: UUID,
    ) -> tuple[EquipmentUnit, Item, Project | None] | None:
        stmt = (
            select(EquipmentUnit, Item, Project)
            .join(Item, EquipmentUnit.item_id == Item.id)
            .outerjoin(Project, EquipmentUnit.current_project_id == Project.id)
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.id == unit_id,
            )
        )
        row = self.db.execute(stmt).first()
        return (row[0], row[1], row[2]) if row else None

    def list_units(
        self,
        organization_id: UUID,
        *,
        search: str | None = None,
        item_id: UUID | None = None,
        status: EquipmentUnitStatus | None = None,
        condition_status: ConditionStatus | None = None,
        current_project_id: UUID | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[EquipmentUnit, Item, Project | None]], int]:
        stmt = (
            select(EquipmentUnit, Item, Project)
            .join(Item, EquipmentUnit.item_id == Item.id)
            .outerjoin(Project, EquipmentUnit.current_project_id == Project.id)
            .where(EquipmentUnit.organization_id == organization_id)
        )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    EquipmentUnit.serial_number.ilike(pattern),
                    Item.item_code.ilike(pattern),
                    Item.description.ilike(pattern),
                )
            )
        if item_id is not None:
            stmt = stmt.where(EquipmentUnit.item_id == item_id)
        if status is not None:
            stmt = stmt.where(EquipmentUnit.status == status.value)
        if condition_status is not None:
            stmt = stmt.where(EquipmentUnit.condition_status == condition_status.value)
        if current_project_id is not None:
            stmt = stmt.where(EquipmentUnit.current_project_id == current_project_id)
        if category and category.strip():
            stmt = stmt.where(Item.category == category.strip())

        total = self.count_query(stmt)
        rows = [
            (row[0], row[1], row[2])
            for row in self.db.execute(
                stmt.order_by(Item.item_code.asc(), EquipmentUnit.serial_number.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_item_for_org(self, organization_id: UUID, item_id: UUID) -> Item | None:
        return self.get_by_id_for_org(Item, item_id, organization_id)

    def get_balance_for_update(
        self,
        organization_id: UUID,
        item_id: UUID,
        ownership_source: str,
    ) -> StockBalance | None:
        return self.db.scalar(
            select(StockBalance)
            .where(
                StockBalance.organization_id == organization_id,
                StockBalance.item_id == item_id,
                StockBalance.ownership_source == ownership_source,
            )
            .with_for_update()
        )

    def list_unit_movements(
        self,
        organization_id: UUID,
        unit_id: UUID,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[StockMovement, Project | None, User]], int]:
        stmt = (
            select(StockMovement, Project, User)
            .join(User, StockMovement.created_by == User.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .where(
                StockMovement.organization_id == organization_id,
                StockMovement.equipment_unit_id == unit_id,
            )
        )
        total = self.count_query(stmt)
        rows = [
            (row[0], row[1], row[2])
            for row in self.db.execute(
                stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total
