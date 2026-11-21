"""Data-access repository for real-time stock balances and category rollups."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.stock_balances.models import StockBalance
from app.shared.enums import OwnershipSource, ProductType
from app.shared.repository import BaseRepository


class StockBalanceRepository(BaseRepository[StockBalance]):
    """Encapsulates tenant-scoped stock balance reads, locks, and SQL category rollups."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

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

    def list_balances(
        self,
        organization_id: UUID,
        *,
        item_id: UUID | None = None,
        product_type: ProductType | None = None,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
        has_replenishment: bool | None = None,
        has_damaged: bool | None = None,
        low_stock_only: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[StockBalance, Item]], int]:
        stmt = (
            select(StockBalance, Item)
            .join(Item, StockBalance.item_id == Item.id)
            .where(StockBalance.organization_id == organization_id)
        )
        if item_id is not None:
            stmt = stmt.where(StockBalance.item_id == item_id)
        if product_type is not None:
            stmt = stmt.where(Item.product_type == product_type.value)
        if category and category.strip():
            stmt = stmt.where(Item.category == category.strip())
        if ownership_source is not None:
            stmt = stmt.where(StockBalance.ownership_source == ownership_source.value)
        if has_replenishment is True:
            stmt = stmt.where(StockBalance.replenishment_qty > 0)
        elif has_replenishment is False:
            stmt = stmt.where(StockBalance.replenishment_qty == 0)
        if has_damaged is True:
            stmt = stmt.where(StockBalance.damaged_qty > 0)
        elif has_damaged is False:
            stmt = stmt.where(StockBalance.damaged_qty == 0)
        if low_stock_only is True:
            stmt = stmt.where(StockBalance.available_qty <= 0)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Item.item_code.ilike(pattern),
                    Item.description.ilike(pattern),
                    Item.category.ilike(pattern),
                )
            )

        total = self.count_query(stmt)
        rows = [
            (row[0], row[1])
            for row in self.db.execute(
                stmt.order_by(Item.item_code.asc(), StockBalance.ownership_source.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def summarize_by_category(
        self,
        organization_id: UUID,
        *,
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> list[dict[str, object]]:
        total_qty_expr = (
            StockBalance.available_qty
            + StockBalance.in_use_qty
            + StockBalance.replenishment_qty
            + StockBalance.damaged_qty
        )
        stmt = (
            select(
                Item.category.label("category"),
                func.count(func.distinct(Item.id)).label("item_count"),
                func.coalesce(func.sum(StockBalance.available_qty), 0).label("available_qty"),
                func.coalesce(func.sum(StockBalance.in_use_qty), 0).label("in_use_qty"),
                func.coalesce(func.sum(StockBalance.replenishment_qty), 0).label(
                    "replenishment_qty"
                ),
                func.coalesce(func.sum(StockBalance.damaged_qty), 0).label("damaged_qty"),
                func.coalesce(func.sum(total_qty_expr), 0).label("total_qty"),
                func.coalesce(
                    func.sum(StockBalance.available_qty * Item.unit_price_aed), 0
                ).label("available_value_aed"),
                func.coalesce(func.sum(StockBalance.in_use_qty * Item.unit_price_aed), 0).label(
                    "in_use_value_aed"
                ),
                func.coalesce(func.sum(total_qty_expr * Item.unit_price_aed), 0).label(
                    "total_value_aed"
                ),
            )
            .join(Item, StockBalance.item_id == Item.id)
            .where(StockBalance.organization_id == organization_id)
        )
        if product_type is not None:
            stmt = stmt.where(Item.product_type == product_type.value)
        if ownership_source is not None:
            stmt = stmt.where(StockBalance.ownership_source == ownership_source.value)

        stmt = stmt.group_by(Item.category).order_by(Item.category.asc())
        results: list[dict[str, object]] = []
        for row in self.db.execute(stmt).mappings().all():
            results.append(
                {
                    "category": str(row["category"]),
                    "item_count": int(row["item_count"]),
                    "available_qty": Decimal(str(row["available_qty"])),
                    "in_use_qty": Decimal(str(row["in_use_qty"])),
                    "replenishment_qty": Decimal(str(row["replenishment_qty"])),
                    "damaged_qty": Decimal(str(row["damaged_qty"])),
                    "total_qty": Decimal(str(row["total_qty"])),
                    "available_value_aed": Decimal(str(row["available_value_aed"])),
                    "in_use_value_aed": Decimal(str(row["in_use_value_aed"])),
                    "total_value_aed": Decimal(str(row["total_value_aed"])),
                }
            )
        return results
