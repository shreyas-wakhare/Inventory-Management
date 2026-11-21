"""Data-access repository for Workshop Replenishment queues and locks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.stock_balances.models import StockBalance
from app.shared.enums import EquipmentUnitStatus, OwnershipSource
from app.shared.repository import BaseRepository


class WorkshopRepository(BaseRepository[EquipmentUnit]):
    """Encapsulates tenant-scoped replenishment queue reads and FOR UPDATE locks."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_replenishment_units(
        self,
        organization_id: UUID,
        *,
        item_id: UUID | None = None,
        category: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[EquipmentUnit, Item, Project | None]], int]:
        stmt = (
            select(EquipmentUnit, Item, Project)
            .join(Item, EquipmentUnit.item_id == Item.id)
            .outerjoin(Project, EquipmentUnit.current_project_id == Project.id)
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.status == EquipmentUnitStatus.REPLENISHMENT.value,
            )
        )
        if item_id is not None:
            stmt = stmt.where(EquipmentUnit.item_id == item_id)
        if category and category.strip():
            stmt = stmt.where(Item.category == category.strip())
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    EquipmentUnit.serial_number.ilike(pattern),
                    Item.item_code.ilike(pattern),
                    Item.description.ilike(pattern),
                )
            )
        total = self.count_query(stmt)
        rows = [
            (r[0], r[1], r[2])
            for r in self.db.execute(
                stmt.order_by(EquipmentUnit.updated_at.asc()).offset(offset).limit(limit)
            ).all()
        ]
        return rows, total

    def list_replenishment_balances(
        self,
        organization_id: UUID,
        *,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[StockBalance, Item]], int]:
        stmt = (
            select(StockBalance, Item)
            .join(Item, StockBalance.item_id == Item.id)
            .where(
                StockBalance.organization_id == organization_id,
                StockBalance.replenishment_qty > 0,
            )
        )
        if category and category.strip():
            stmt = stmt.where(Item.category == category.strip())
        if ownership_source is not None:
            stmt = stmt.where(StockBalance.ownership_source == ownership_source.value)

        total = self.count_query(stmt)
        rows = [
            (r[0], r[1])
            for r in self.db.execute(
                stmt.order_by(StockBalance.replenishment_qty.desc(), Item.item_code.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_item_for_org(self, organization_id: UUID, item_id: UUID) -> Item | None:
        return self.get_by_id_for_org(Item, item_id, organization_id)

    def get_unit_for_update(
        self,
        organization_id: UUID,
        unit_id: UUID,
    ) -> EquipmentUnit | None:
        return self.get_by_id_for_org(EquipmentUnit, unit_id, organization_id, for_update=True)

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
