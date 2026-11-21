"""Data-access repository for the items catalog with single-query stock aggregations."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.stock_balances.models import StockBalance
from app.shared.enums import ProductType
from app.shared.repository import BaseRepository


class ItemRepository(BaseRepository[Item]):
    """Encapsulates tenant-scoped SQLAlchemy 2.0 queries for catalog items."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(self, organization_id: UUID, item_id: UUID) -> Item | None:
        return self.get_by_id_for_org(Item, item_id, organization_id)

    def get_by_code(self, organization_id: UUID, item_code: str) -> Item | None:
        return self.db.scalar(
            select(Item).where(
                Item.organization_id == organization_id,
                Item.item_code == item_code.strip().upper(),
            )
        )

    def list_items_with_stock(
        self,
        organization_id: UUID,
        *,
        search: str | None = None,
        product_type: ProductType | None = None,
        category: str | None = None,
        sub_category: str | None = None,
        is_active: bool | None = None,
        sort_by: str = "item_code",
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[Item, Decimal, Decimal, Decimal, Decimal]], int]:
        bal_agg = (
            select(
                StockBalance.item_id.label("item_id"),
                func.coalesce(func.sum(StockBalance.available_qty), 0).label("available_qty"),
                func.coalesce(func.sum(StockBalance.in_use_qty), 0).label("in_use_qty"),
                func.coalesce(func.sum(StockBalance.replenishment_qty), 0).label(
                    "replenishment_qty"
                ),
                func.coalesce(func.sum(StockBalance.damaged_qty), 0).label("damaged_qty"),
            )
            .where(StockBalance.organization_id == organization_id)
            .group_by(StockBalance.item_id)
            .subquery()
        )

        avail_col = func.coalesce(bal_agg.c.available_qty, 0).label("available_qty")
        in_use_col = func.coalesce(bal_agg.c.in_use_qty, 0).label("in_use_qty")
        repl_col = func.coalesce(bal_agg.c.replenishment_qty, 0).label("replenishment_qty")
        dmg_col = func.coalesce(bal_agg.c.damaged_qty, 0).label("damaged_qty")

        stmt = (
            select(Item, avail_col, in_use_col, repl_col, dmg_col)
            .outerjoin(bal_agg, bal_agg.c.item_id == Item.id)
            .where(Item.organization_id == organization_id)
        )

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Item.item_code.ilike(pattern),
                    Item.description.ilike(pattern),
                    Item.category.ilike(pattern),
                    Item.sub_category.ilike(pattern),
                )
            )
        if product_type is not None:
            stmt = stmt.where(Item.product_type == product_type.value)
        if category and category.strip():
            stmt = stmt.where(Item.category == category.strip())
        if sub_category and sub_category.strip():
            stmt = stmt.where(Item.sub_category == sub_category.strip())
        if is_active is not None:
            stmt = stmt.where(Item.is_active.is_(is_active))

        total = self.count_query(stmt)

        order_map = {
            "item_code": Item.item_code.asc(),
            "category": Item.category.asc(),
            "unit_price_aed": Item.unit_price_aed.desc(),
            "available_qty": avail_col.desc(),
        }
        order_expr = order_map.get(sort_by, Item.item_code.asc())

        rows = [
            (
                row[0],
                Decimal(str(row[1])),
                Decimal(str(row[2])),
                Decimal(str(row[3])),
                Decimal(str(row[4])),
            )
            for row in self.db.execute(
                stmt.order_by(order_expr, Item.item_code.asc()).offset(offset).limit(limit)
            ).all()
        ]
        return rows, total

    def get_category_facets(
        self,
        organization_id: UUID,
        *,
        product_type: ProductType | None = None,
    ) -> list[tuple[str, list[str], int]]:
        stmt = select(Item.category, Item.sub_category, func.count(Item.id)).where(
            Item.organization_id == organization_id,
            Item.is_active.is_(True),
        )
        if product_type is not None:
            stmt = stmt.where(Item.product_type == product_type.value)
        stmt = stmt.group_by(Item.category, Item.sub_category).order_by(Item.category.asc())

        sub_map: dict[str, set[str]] = defaultdict(set)
        counts: dict[str, int] = defaultdict(int)
        for cat, sub_cat, cnt in self.db.execute(stmt).all():
            counts[cat] += int(cnt)
            if sub_cat:
                sub_map[cat].add(sub_cat)

        return [(cat, sorted(sub_map[cat]), counts[cat]) for cat in sorted(counts)]

    def get_balances_for_item(self, organization_id: UUID, item_id: UUID) -> list[StockBalance]:
        return list(
            self.db.scalars(
                select(StockBalance)
                .where(
                    StockBalance.organization_id == organization_id,
                    StockBalance.item_id == item_id,
                )
                .order_by(StockBalance.ownership_source.asc())
            ).all()
        )

    def get_unit_status_counts(self, organization_id: UUID, item_id: UUID) -> dict[str, int]:
        rows = self.db.execute(
            select(EquipmentUnit.status, func.count(EquipmentUnit.id))
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.item_id == item_id,
            )
            .group_by(EquipmentUnit.status)
        ).all()
        return {str(status): int(cnt) for status, cnt in rows}
