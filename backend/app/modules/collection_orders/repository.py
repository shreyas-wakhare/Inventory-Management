"""Data-access repository for Collection Orders with deterministic FOR UPDATE locking."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.collection_orders.models import CollectionOrder, CollectionOrderLine
from app.modules.delivery_orders.models import DeliveryOrder, DeliveryOrderLine
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.stock_balances.models import StockBalance
from app.modules.users.models import User
from app.shared.enums import CollectionOrderStatus
from app.shared.repository import BaseRepository


class CollectionOrderRepository(BaseRepository[CollectionOrder]):
    """Encapsulates tenant-scoped queries and ordered row locks for CO receipt workflows."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(
        self,
        organization_id: UUID,
        co_id: UUID,
        *,
        for_update: bool = False,
        with_lines: bool = True,
    ) -> CollectionOrder | None:
        stmt = select(CollectionOrder).where(
            CollectionOrder.id == co_id,
            CollectionOrder.organization_id == organization_id,
        )
        if with_lines:
            stmt = stmt.options(selectinload(CollectionOrder.lines))
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def get_by_number(self, organization_id: UUID, co_number: str) -> CollectionOrder | None:
        return self.db.scalar(
            select(CollectionOrder).where(
                CollectionOrder.organization_id == organization_id,
                CollectionOrder.co_number == co_number.strip().upper(),
            )
        )

    def get_project_for_org(self, organization_id: UUID, project_id: UUID) -> Project | None:
        return self.get_by_id_for_org(Project, project_id, organization_id)

    def get_delivery_order_for_org(
        self,
        organization_id: UUID,
        do_id: UUID,
        *,
        for_update: bool = False,
    ) -> DeliveryOrder | None:
        stmt = (
            select(DeliveryOrder)
            .options(selectinload(DeliveryOrder.lines))
            .where(
                DeliveryOrder.id == do_id,
                DeliveryOrder.organization_id == organization_id,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def get_items_by_ids(self, organization_id: UUID, item_ids: list[UUID]) -> dict[UUID, Item]:
        if not item_ids:
            return {}
        rows = self.db.scalars(
            select(Item).where(
                Item.organization_id == organization_id,
                Item.id.in_(item_ids),
            )
        ).all()
        return {it.id: it for it in rows}

    def lock_units_ordered(
        self,
        organization_id: UUID,
        unit_ids: list[UUID],
    ) -> dict[UUID, EquipmentUnit]:
        if not unit_ids:
            return {}
        rows = self.db.scalars(
            select(EquipmentUnit)
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.id.in_(sorted(set(unit_ids))),
            )
            .order_by(EquipmentUnit.id.asc())
            .with_for_update()
        ).all()
        return {u.id: u for u in rows}

    def lock_balances_ordered(
        self,
        organization_id: UUID,
        item_ids: list[UUID],
    ) -> dict[tuple[UUID, str], StockBalance]:
        if not item_ids:
            return {}
        rows = self.db.scalars(
            select(StockBalance)
            .where(
                StockBalance.organization_id == organization_id,
                StockBalance.item_id.in_(sorted(set(item_ids))),
            )
            .order_by(StockBalance.id.asc())
            .with_for_update()
        ).all()
        return {(b.item_id, b.ownership_source): b for b in rows}

    def lock_do_lines_ordered(
        self,
        organization_id: UUID,
        do_line_ids: list[UUID],
    ) -> dict[UUID, tuple[DeliveryOrderLine, DeliveryOrder]]:
        if not do_line_ids:
            return {}
        rows = self.db.execute(
            select(DeliveryOrderLine, DeliveryOrder)
            .join(DeliveryOrder, DeliveryOrderLine.delivery_order_id == DeliveryOrder.id)
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrderLine.id.in_(sorted(set(do_line_ids))),
            )
            .order_by(DeliveryOrderLine.id.asc())
            .with_for_update()
        ).all()
        return {r[0].id: (r[0], r[1]) for r in rows}

    def find_matching_open_do_line_for_update(
        self,
        organization_id: UUID,
        *,
        project_id: UUID,
        delivery_order_id: UUID | None,
        item_id: UUID,
        equipment_unit_id: UUID | None,
        ownership_source: str,
    ) -> tuple[DeliveryOrderLine, DeliveryOrder] | None:
        stmt = (
            select(DeliveryOrderLine, DeliveryOrder)
            .join(DeliveryOrder, DeliveryOrderLine.delivery_order_id == DeliveryOrder.id)
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.project_id == project_id,
                DeliveryOrder.status.in_(["DISPATCHED", "PARTIALLY_RETURNED"]),
                DeliveryOrderLine.item_id == item_id,
                DeliveryOrderLine.ownership_source == ownership_source,
                (
                    DeliveryOrderLine.dispatched_qty
                    - DeliveryOrderLine.returned_qty
                    - DeliveryOrderLine.lost_qty
                )
                > 0,
            )
        )
        if delivery_order_id is not None:
            stmt = stmt.where(DeliveryOrder.id == delivery_order_id)
        if equipment_unit_id is not None:
            stmt = stmt.where(DeliveryOrderLine.equipment_unit_id == equipment_unit_id)
        else:
            stmt = stmt.where(DeliveryOrderLine.equipment_unit_id.is_(None))
        row = self.db.execute(
            stmt.order_by(DeliveryOrder.dispatch_date.asc(), DeliveryOrderLine.id.asc())
            .limit(1)
            .with_for_update()
        ).first()
        return (row[0], row[1]) if row else None

    def find_reconciliation_for_update(
        self,
        organization_id: UUID,
        delivery_order_id: UUID,
        item_id: UUID,
        equipment_unit_id: UUID | None,
    ) -> ReconciliationRecord | None:
        stmt = select(ReconciliationRecord).where(
            ReconciliationRecord.organization_id == organization_id,
            ReconciliationRecord.delivery_order_id == delivery_order_id,
            ReconciliationRecord.item_id == item_id,
        )
        if equipment_unit_id is not None:
            stmt = stmt.where(ReconciliationRecord.equipment_unit_id == equipment_unit_id)
        else:
            stmt = stmt.where(ReconciliationRecord.equipment_unit_id.is_(None))
        return self.db.scalar(stmt.with_for_update())

    def list_orders(
        self,
        organization_id: UUID,
        *,
        project_id: UUID | None = None,
        delivery_order_id: UUID | None = None,
        status: CollectionOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[CollectionOrder, Project, DeliveryOrder | None, User, int, Decimal]], int]:
        line_agg = (
            select(
                CollectionOrderLine.collection_order_id.label("co_id"),
                func.count(CollectionOrderLine.id).label("line_count"),
                func.coalesce(func.sum(CollectionOrderLine.returned_qty), 0).label("returned"),
            )
            .group_by(CollectionOrderLine.collection_order_id)
            .subquery()
        )

        stmt = (
            select(
                CollectionOrder,
                Project,
                DeliveryOrder,
                User,
                func.coalesce(line_agg.c.line_count, 0),
                func.coalesce(line_agg.c.returned, 0),
            )
            .join(Project, CollectionOrder.project_id == Project.id)
            .join(User, CollectionOrder.created_by == User.id)
            .outerjoin(DeliveryOrder, CollectionOrder.delivery_order_id == DeliveryOrder.id)
            .outerjoin(line_agg, line_agg.c.co_id == CollectionOrder.id)
            .where(CollectionOrder.organization_id == organization_id)
        )
        if project_id is not None:
            stmt = stmt.where(CollectionOrder.project_id == project_id)
        if delivery_order_id is not None:
            stmt = stmt.where(CollectionOrder.delivery_order_id == delivery_order_id)
        if status is not None:
            stmt = stmt.where(CollectionOrder.status == status.value)
        if date_from is not None:
            stmt = stmt.where(CollectionOrder.collection_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(CollectionOrder.collection_date <= date_to)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    CollectionOrder.co_number.ilike(pattern),
                    Project.project_code.ilike(pattern),
                    DeliveryOrder.do_number.ilike(pattern),
                )
            )

        total = self.count_query(stmt)
        rows = [
            (r[0], r[1], r[2], r[3], int(r[4]), Decimal(str(r[5])))
            for r in self.db.execute(
                stmt.order_by(
                    CollectionOrder.collection_date.desc(),
                    CollectionOrder.created_at.desc(),
                )
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_order_detail_parts(
        self,
        organization_id: UUID,
        co_id: UUID,
    ) -> tuple[
        CollectionOrder,
        Project,
        DeliveryOrder | None,
        User,
        list[tuple[CollectionOrderLine, Item, EquipmentUnit | None]],
    ] | None:
        header = self.db.execute(
            select(CollectionOrder, Project, DeliveryOrder, User)
            .join(Project, CollectionOrder.project_id == Project.id)
            .join(User, CollectionOrder.created_by == User.id)
            .outerjoin(DeliveryOrder, CollectionOrder.delivery_order_id == DeliveryOrder.id)
            .where(
                CollectionOrder.organization_id == organization_id,
                CollectionOrder.id == co_id,
            )
        ).first()
        if header is None:
            return None

        line_rows = [
            (r[0], r[1], r[2])
            for r in self.db.execute(
                select(CollectionOrderLine, Item, EquipmentUnit)
                .join(Item, CollectionOrderLine.item_id == Item.id)
                .outerjoin(EquipmentUnit, CollectionOrderLine.equipment_unit_id == EquipmentUnit.id)
                .where(CollectionOrderLine.collection_order_id == co_id)
                .order_by(CollectionOrderLine.created_at.asc())
            ).all()
        ]
        return header[0], header[1], header[2], header[3], line_rows
