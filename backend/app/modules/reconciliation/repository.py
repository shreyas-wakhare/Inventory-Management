"""Data-access repository for reconciliation records and atomic write-off locks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, selectinload

from app.modules.delivery_orders.models import DeliveryOrder, DeliveryOrderLine
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_movements.models import StockMovement
from app.modules.users.models import User
from app.shared.enums import ReconciliationStatus
from app.shared.repository import BaseRepository


class ReconciliationRepository(BaseRepository[ReconciliationRecord]):
    """Encapsulates tenant-scoped reconciliation queries and FOR UPDATE locks."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_for_update(
        self,
        organization_id: UUID,
        recon_id: UUID,
    ) -> ReconciliationRecord | None:
        return self.get_by_id_for_org(
            ReconciliationRecord,
            recon_id,
            organization_id,
            for_update=True,
        )

    def list_records(
        self,
        organization_id: UUID,
        *,
        project_id: UUID | None = None,
        delivery_order_id: UUID | None = None,
        item_id: UUID | None = None,
        status: ReconciliationStatus | None = None,
        only_with_variance: bool | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[
        list[
            tuple[
                ReconciliationRecord,
                Project,
                DeliveryOrder,
                Item,
                EquipmentUnit | None,
                User | None,
            ]
        ],
        int,
    ]:
        resolver = aliased(User)
        stmt = (
            select(
                ReconciliationRecord,
                Project,
                DeliveryOrder,
                Item,
                EquipmentUnit,
                resolver,
            )
            .join(Project, ReconciliationRecord.project_id == Project.id)
            .join(DeliveryOrder, ReconciliationRecord.delivery_order_id == DeliveryOrder.id)
            .join(Item, ReconciliationRecord.item_id == Item.id)
            .outerjoin(EquipmentUnit, ReconciliationRecord.equipment_unit_id == EquipmentUnit.id)
            .outerjoin(resolver, ReconciliationRecord.resolved_by == resolver.id)
            .where(ReconciliationRecord.organization_id == organization_id)
        )
        if project_id is not None:
            stmt = stmt.where(ReconciliationRecord.project_id == project_id)
        if delivery_order_id is not None:
            stmt = stmt.where(ReconciliationRecord.delivery_order_id == delivery_order_id)
        if item_id is not None:
            stmt = stmt.where(ReconciliationRecord.item_id == item_id)
        if status is not None:
            stmt = stmt.where(ReconciliationRecord.reconciliation_status == status.value)
        if only_with_variance is True:
            stmt = stmt.where(ReconciliationRecord.variance_qty > 0)

        total = self.count_query(stmt)
        rows = [
            (r[0], r[1], r[2], r[3], r[4], r[5])
            for r in self.db.execute(
                stmt.order_by(ReconciliationRecord.updated_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_record_joined(
        self,
        organization_id: UUID,
        recon_id: UUID,
    ) -> tuple[
        ReconciliationRecord,
        Project,
        DeliveryOrder,
        Item,
        EquipmentUnit | None,
        User | None,
    ] | None:
        resolver = aliased(User)
        row = self.db.execute(
            select(
                ReconciliationRecord,
                Project,
                DeliveryOrder,
                Item,
                EquipmentUnit,
                resolver,
            )
            .join(Project, ReconciliationRecord.project_id == Project.id)
            .join(DeliveryOrder, ReconciliationRecord.delivery_order_id == DeliveryOrder.id)
            .join(Item, ReconciliationRecord.item_id == Item.id)
            .outerjoin(EquipmentUnit, ReconciliationRecord.equipment_unit_id == EquipmentUnit.id)
            .outerjoin(resolver, ReconciliationRecord.resolved_by == resolver.id)
            .where(
                ReconciliationRecord.organization_id == organization_id,
                ReconciliationRecord.id == recon_id,
            )
        ).first()
        return (row[0], row[1], row[2], row[3], row[4], row[5]) if row else None

    def get_related_movements(
        self,
        organization_id: UUID,
        *,
        project_id: UUID,
        item_id: UUID,
        equipment_unit_id: UUID | None,
    ) -> list[tuple[StockMovement, Item, EquipmentUnit | None, Project | None, User]]:
        stmt = (
            select(StockMovement, Item, EquipmentUnit, Project, User)
            .join(Item, StockMovement.item_id == Item.id)
            .join(User, StockMovement.created_by == User.id)
            .outerjoin(EquipmentUnit, StockMovement.equipment_unit_id == EquipmentUnit.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .where(
                StockMovement.organization_id == organization_id,
                StockMovement.project_id == project_id,
                StockMovement.item_id == item_id,
            )
        )
        if equipment_unit_id is not None:
            stmt = stmt.where(StockMovement.equipment_unit_id == equipment_unit_id)
        else:
            stmt = stmt.where(StockMovement.equipment_unit_id.is_(None))
        return [
            (r[0], r[1], r[2], r[3], r[4])
            for r in self.db.execute(
                stmt.order_by(StockMovement.created_at.desc()).limit(50)
            ).all()
        ]

    def lock_matching_do_line(
        self,
        delivery_order_id: UUID,
        item_id: UUID,
        equipment_unit_id: UUID | None,
        ownership_source: str,
    ) -> DeliveryOrderLine | None:
        stmt = select(DeliveryOrderLine).where(
            DeliveryOrderLine.delivery_order_id == delivery_order_id,
            DeliveryOrderLine.item_id == item_id,
            DeliveryOrderLine.ownership_source == ownership_source,
        )
        if equipment_unit_id is not None:
            stmt = stmt.where(DeliveryOrderLine.equipment_unit_id == equipment_unit_id)
        else:
            stmt = stmt.where(DeliveryOrderLine.equipment_unit_id.is_(None))
        return self.db.scalar(stmt.order_by(DeliveryOrderLine.id.asc()).limit(1).with_for_update())

    def lock_delivery_order(
        self,
        organization_id: UUID,
        delivery_order_id: UUID,
    ) -> DeliveryOrder | None:
        return self.db.scalar(
            select(DeliveryOrder)
            .options(selectinload(DeliveryOrder.lines))
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.id == delivery_order_id,
            )
            .with_for_update()
        )

    def lock_balance(
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

    def lock_unit(self, organization_id: UUID, unit_id: UUID) -> EquipmentUnit | None:
        return self.get_by_id_for_org(EquipmentUnit, unit_id, organization_id, for_update=True)
