"""Data-access repository for Delivery Orders with deterministic FOR UPDATE locking."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.delivery_orders.models import DeliveryOrder, DeliveryOrderLine
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.stock_balances.models import StockBalance
from app.modules.users.models import User
from app.shared.enums import DeliveryOrderStatus
from app.shared.repository import BaseRepository


class DeliveryOrderRepository(BaseRepository[DeliveryOrder]):
    """Encapsulates tenant-scoped queries and deadlock-free locks for DO workflows."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(
        self,
        organization_id: UUID,
        do_id: UUID,
        *,
        for_update: bool = False,
        with_lines: bool = True,
    ) -> DeliveryOrder | None:
        stmt = select(DeliveryOrder).where(
            DeliveryOrder.id == do_id,
            DeliveryOrder.organization_id == organization_id,
        )
        if with_lines:
            stmt = stmt.options(selectinload(DeliveryOrder.lines))
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def get_by_number(self, organization_id: UUID, do_number: str) -> DeliveryOrder | None:
        return self.db.scalar(
            select(DeliveryOrder).where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.do_number == do_number.strip().upper(),
            )
        )

    def get_project_for_org(self, organization_id: UUID, project_id: UUID) -> Project | None:
        return self.get_by_id_for_org(Project, project_id, organization_id)

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
        status: DeliveryOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[DeliveryOrder, Project, User, int, Decimal, Decimal, Decimal]], int]:
        line_agg = (
            select(
                DeliveryOrderLine.delivery_order_id.label("do_id"),
                func.count(DeliveryOrderLine.id).label("line_count"),
                func.coalesce(func.sum(DeliveryOrderLine.dispatched_qty), 0).label("dispatched"),
                func.coalesce(func.sum(DeliveryOrderLine.returned_qty), 0).label("returned"),
                func.coalesce(
                    func.sum(
                        DeliveryOrderLine.dispatched_qty
                        - DeliveryOrderLine.returned_qty
                        - DeliveryOrderLine.lost_qty
                    ),
                    0,
                ).label("outstanding"),
            )
            .group_by(DeliveryOrderLine.delivery_order_id)
            .subquery()
        )

        stmt = (
            select(
                DeliveryOrder,
                Project,
                User,
                func.coalesce(line_agg.c.line_count, 0),
                func.coalesce(line_agg.c.dispatched, 0),
                func.coalesce(line_agg.c.returned, 0),
                func.coalesce(line_agg.c.outstanding, 0),
            )
            .join(Project, DeliveryOrder.project_id == Project.id)
            .join(User, DeliveryOrder.created_by == User.id)
            .outerjoin(line_agg, line_agg.c.do_id == DeliveryOrder.id)
            .where(DeliveryOrder.organization_id == organization_id)
        )
        if project_id is not None:
            stmt = stmt.where(DeliveryOrder.project_id == project_id)
        if status is not None:
            stmt = stmt.where(DeliveryOrder.status == status.value)
        if date_from is not None:
            stmt = stmt.where(DeliveryOrder.dispatch_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(DeliveryOrder.dispatch_date <= date_to)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    DeliveryOrder.do_number.ilike(pattern),
                    Project.project_code.ilike(pattern),
                    Project.project_name.ilike(pattern),
                )
            )

        total = self.count_query(stmt)
        rows = [
            (
                r[0],
                r[1],
                r[2],
                int(r[3]),
                Decimal(str(r[4])),
                Decimal(str(r[5])),
                Decimal(str(r[6])),
            )
            for r in self.db.execute(
                stmt.order_by(DeliveryOrder.dispatch_date.desc(), DeliveryOrder.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_order_detail_parts(
        self,
        organization_id: UUID,
        do_id: UUID,
    ) -> tuple[
        DeliveryOrder,
        Project,
        User,
        list[tuple[DeliveryOrderLine, Item, EquipmentUnit | None]],
    ] | None:
        header = self.db.execute(
            select(DeliveryOrder, Project, User)
            .join(Project, DeliveryOrder.project_id == Project.id)
            .join(User, DeliveryOrder.created_by == User.id)
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.id == do_id,
            )
        ).first()
        if header is None:
            return None

        line_rows = [
            (r[0], r[1], r[2])
            for r in self.db.execute(
                select(DeliveryOrderLine, Item, EquipmentUnit)
                .join(Item, DeliveryOrderLine.item_id == Item.id)
                .outerjoin(EquipmentUnit, DeliveryOrderLine.equipment_unit_id == EquipmentUnit.id)
                .where(DeliveryOrderLine.delivery_order_id == do_id)
                .order_by(DeliveryOrderLine.created_at.asc())
            ).all()
        ]
        return header[0], header[1], header[2], line_rows
