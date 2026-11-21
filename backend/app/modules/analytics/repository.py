"""Server-side SQL aggregation repository for Next.js dashboard KPIs and charts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.modules.delivery_orders.models import DeliveryOrder, DeliveryOrderLine
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.stock_balances.models import StockBalance
from app.shared.enums import OwnershipSource, ProductType, ProjectStatus
from app.shared.repository import BaseRepository


class AnalyticsRepository(BaseRepository[object]):
    """Executes single-pass PostgreSQL GROUP BY and generate_series aggregations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_kpi_aggregates(
        self,
        organization_id: UUID,
        *,
        ownership_source: OwnershipSource | None = None,
    ) -> dict[str, Any]:
        # 1. Catalog counts
        cat_row = self.db.execute(
            select(
                func.count(Item.id).label("total_items"),
                func.coalesce(
                    func.sum(case((Item.product_type == "ASSET", 1), else_=0)), 0
                ).label("asset_skus"),
                func.coalesce(
                    func.sum(case((Item.product_type == "ACCESSORY", 1), else_=0)), 0
                ).label("accessory_skus"),
            ).where(Item.organization_id == organization_id, Item.is_active.is_(True))
        ).mappings().one()

        # 2. Serialized unit counts by status
        unit_rows = self.db.execute(
            select(EquipmentUnit.status, func.count(EquipmentUnit.id))
            .where(EquipmentUnit.organization_id == organization_id)
            .group_by(EquipmentUnit.status)
        ).all()
        unit_counts = {str(status): int(cnt) for status, cnt in unit_rows}
        total_units = sum(unit_counts.values())

        # 3. Bucket quantities & AED values
        bal_stmt = (
            select(
                func.coalesce(func.sum(StockBalance.available_qty), 0).label("avail_qty"),
                func.coalesce(func.sum(StockBalance.in_use_qty), 0).label("in_use_qty"),
                func.coalesce(func.sum(StockBalance.replenishment_qty), 0).label("repl_qty"),
                func.coalesce(func.sum(StockBalance.damaged_qty), 0).label("dmg_qty"),
                func.coalesce(
                    func.sum(StockBalance.available_qty * Item.unit_price_aed), 0
                ).label("avail_val"),
                func.coalesce(
                    func.sum(StockBalance.in_use_qty * Item.unit_price_aed), 0
                ).label("in_use_val"),
                func.coalesce(
                    func.sum(StockBalance.replenishment_qty * Item.unit_price_aed), 0
                ).label("repl_val"),
                func.coalesce(
                    func.sum(StockBalance.damaged_qty * Item.unit_price_aed), 0
                ).label("dmg_val"),
            )
            .join(Item, StockBalance.item_id == Item.id)
            .where(StockBalance.organization_id == organization_id)
        )
        if ownership_source is not None:
            bal_stmt = bal_stmt.where(StockBalance.ownership_source == ownership_source.value)
        bal_row = self.db.execute(bal_stmt).mappings().one()

        # 4. Active projects
        active_projects = int(
            self.db.scalar(
                select(func.count(Project.id)).where(
                    Project.organization_id == organization_id,
                    Project.status == ProjectStatus.ACTIVE.value,
                )
            )
            or 0
        )

        # 5. Open discrepancies & variance AED
        recon_row = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (ReconciliationRecord.reconciliation_status == "DISCREPANCY", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("open_discrepancies"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ReconciliationRecord.reconciliation_status.in_(
                                    ["OPEN", "DISCREPANCY"]
                                ),
                                ReconciliationRecord.variance_qty * Item.unit_price_aed,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("variance_val"),
            )
            .join(Item, ReconciliationRecord.item_id == Item.id)
            .where(ReconciliationRecord.organization_id == organization_id)
        ).mappings().one()

        return {
            "total_items": int(cat_row["total_items"]),
            "asset_skus": int(cat_row["asset_skus"]),
            "accessory_skus": int(cat_row["accessory_skus"]),
            "total_units": total_units,
            "unit_counts": unit_counts,
            "bal": bal_row,
            "active_projects": active_projects,
            "open_discrepancies": int(recon_row["open_discrepancies"]),
            "variance_val": Decimal(str(recon_row["variance_val"])),
        }

    def get_stock_distribution(
        self,
        organization_id: UUID,
        *,
        group_by: Literal["category", "product_type", "ownership_source"],
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> list[dict[str, Any]]:
        group_col_map = {
            "category": Item.category,
            "product_type": Item.product_type,
            "ownership_source": StockBalance.ownership_source,
        }
        group_col = group_col_map[group_by]
        total_qty_expr = (
            StockBalance.available_qty
            + StockBalance.in_use_qty
            + StockBalance.replenishment_qty
            + StockBalance.damaged_qty
        )

        stmt = (
            select(
                group_col.label("label"),
                func.coalesce(func.sum(StockBalance.available_qty), 0).label("available_qty"),
                func.coalesce(func.sum(StockBalance.in_use_qty), 0).label("in_use_qty"),
                func.coalesce(func.sum(StockBalance.replenishment_qty), 0).label(
                    "replenishment_qty"
                ),
                func.coalesce(func.sum(StockBalance.damaged_qty), 0).label("damaged_qty"),
                func.coalesce(func.sum(total_qty_expr), 0).label("total_qty"),
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

        stmt = stmt.group_by(group_col).order_by(group_col.asc())
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def get_project_utilization(
        self,
        organization_id: UUID,
        *,
        status: ProjectStatus | None = ProjectStatus.ACTIVE,
        limit: int = 10,
        sort_by: Literal["deployed_value_aed", "deployed_units", "outstanding_qty"] = "deployed_value_aed",
    ) -> list[dict[str, Any]]:
        unit_sub = (
            select(
                EquipmentUnit.current_project_id.label("project_id"),
                func.count(EquipmentUnit.id).label("deployed_units_count"),
            )
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.current_project_id.is_not(None),
            )
            .group_by(EquipmentUnit.current_project_id)
            .subquery()
        )

        open_dos_sub = (
            select(
                DeliveryOrder.project_id.label("project_id"),
                func.count(DeliveryOrder.id).label("open_dos_count"),
            )
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.status.in_(["DISPATCHED", "PARTIALLY_RETURNED"]),
            )
            .group_by(DeliveryOrder.project_id)
            .subquery()
        )

        remaining_expr = (
            DeliveryOrderLine.dispatched_qty
            - DeliveryOrderLine.returned_qty
            - DeliveryOrderLine.lost_qty
        )
        exposure_sub = (
            select(
                DeliveryOrder.project_id.label("project_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (Item.is_serialized.is_(False), remaining_expr),
                            else_=0,
                        )
                    ),
                    0,
                ).label("bulk_in_use_qty"),
                func.coalesce(func.sum(remaining_expr), 0).label("outstanding_variance_qty"),
                func.coalesce(func.sum(remaining_expr * Item.unit_price_aed), 0).label(
                    "deployed_value_aed"
                ),
            )
            .join(DeliveryOrder, DeliveryOrderLine.delivery_order_id == DeliveryOrder.id)
            .join(Item, DeliveryOrderLine.item_id == Item.id)
            .where(
                DeliveryOrder.organization_id == organization_id,
                DeliveryOrder.status.in_(["DISPATCHED", "PARTIALLY_RETURNED"]),
            )
            .group_by(DeliveryOrder.project_id)
            .subquery()
        )

        deployed_units_col = func.coalesce(unit_sub.c.deployed_units_count, 0).label(
            "deployed_units_count"
        )
        bulk_qty_col = func.coalesce(exposure_sub.c.bulk_in_use_qty, 0).label("bulk_in_use_qty")
        open_dos_col = func.coalesce(open_dos_sub.c.open_dos_count, 0).label("open_dos_count")
        out_var_col = func.coalesce(exposure_sub.c.outstanding_variance_qty, 0).label(
            "outstanding_variance_qty"
        )
        dep_val_col = func.coalesce(exposure_sub.c.deployed_value_aed, 0).label(
            "deployed_value_aed"
        )

        stmt = (
            select(
                Project.id.label("project_id"),
                Project.project_code,
                Project.project_name,
                deployed_units_col,
                bulk_qty_col,
                open_dos_col,
                out_var_col,
                dep_val_col,
            )
            .outerjoin(unit_sub, unit_sub.c.project_id == Project.id)
            .outerjoin(open_dos_sub, open_dos_sub.c.project_id == Project.id)
            .outerjoin(exposure_sub, exposure_sub.c.project_id == Project.id)
            .where(Project.organization_id == organization_id)
        )
        if status is not None:
            stmt = stmt.where(Project.status == status.value)

        order_map = {
            "deployed_value_aed": dep_val_col.desc(),
            "deployed_units": deployed_units_col.desc(),
            "outstanding_qty": out_var_col.desc(),
        }
        stmt = stmt.order_by(order_map[sort_by], Project.project_code.asc()).limit(limit)
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def get_movement_trends(
        self,
        organization_id: UUID,
        *,
        granularity: Literal["day", "week"],
        date_from: date,
        date_to: date,
        product_type: ProductType | None = None,
        project_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        step = "1 day" if granularity == "day" else "1 week"
        extra_filters: list[str] = []
        params: dict[str, Any] = {
            "granularity": granularity,
            "date_from": date_from,
            "date_to": date_to,
            "org_id": organization_id,
        }
        if product_type is not None:
            extra_filters.append("AND i.product_type = :product_type")
            params["product_type"] = product_type.value
        if project_id is not None:
            extra_filters.append("AND sm.project_id = :project_id")
            params["project_id"] = project_id

        extra_where = "\n                  ".join(extra_filters)
        sql = text(
            f"""
            WITH periods AS (
                SELECT date_trunc(:granularity, d)::date AS period_start
                FROM generate_series(
                    date_trunc(:granularity, CAST(:date_from AS timestamp)),
                    date_trunc(:granularity, CAST(:date_to AS timestamp)),
                    INTERVAL '{step}'
                ) AS d
            ),
            agg AS (
                SELECT
                    date_trunc(:granularity, sm.created_at AT TIME ZONE 'UTC')::date AS period_start,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'DO_DISPATCH' THEN sm.quantity ELSE 0 END), 0) AS dispatched_qty,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'CO_RETURN_AVAILABLE' THEN sm.quantity ELSE 0 END), 0) AS returned_available_qty,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'CO_RETURN_REPLENISHMENT' THEN sm.quantity ELSE 0 END), 0) AS returned_replenishment_qty,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'CO_RETURN_DAMAGED' THEN sm.quantity ELSE 0 END), 0) AS returned_damaged_qty,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'REPLENISHMENT_COMPLETE' THEN sm.quantity ELSE 0 END), 0) AS replenishment_completed_qty,
                    COALESCE(SUM(CASE WHEN sm.movement_type = 'LOSS_WRITE_OFF' THEN sm.quantity ELSE 0 END), 0) AS loss_write_off_qty
                FROM stock_movements sm
                JOIN items i ON i.id = sm.item_id
                WHERE sm.organization_id = :org_id
                  AND (sm.created_at AT TIME ZONE 'UTC')::date >= :date_from
                  AND (sm.created_at AT TIME ZONE 'UTC')::date <= :date_to
                  {extra_where}
                GROUP BY 1
            )
            SELECT
                p.period_start,
                COALESCE(a.dispatched_qty, 0) AS dispatched_qty,
                COALESCE(a.returned_available_qty, 0) AS returned_available_qty,
                COALESCE(a.returned_replenishment_qty, 0) AS returned_replenishment_qty,
                COALESCE(a.returned_damaged_qty, 0) AS returned_damaged_qty,
                COALESCE(a.replenishment_completed_qty, 0) AS replenishment_completed_qty,
                COALESCE(a.loss_write_off_qty, 0) AS loss_write_off_qty
            FROM periods p
            LEFT JOIN agg a ON a.period_start = p.period_start
            ORDER BY p.period_start ASC
            """
        )
        rows = self.db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def get_reconciliation_health(
        self,
        organization_id: UUID,
        *,
        project_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                ReconciliationRecord.reconciliation_status.label("status"),
                func.count(ReconciliationRecord.id).label("record_count"),
                func.coalesce(func.sum(ReconciliationRecord.outgoing_qty), 0).label(
                    "total_outgoing_qty"
                ),
                func.coalesce(func.sum(ReconciliationRecord.incoming_qty), 0).label(
                    "total_incoming_qty"
                ),
                func.coalesce(func.sum(ReconciliationRecord.lost_qty), 0).label("total_lost_qty"),
                func.coalesce(func.sum(ReconciliationRecord.variance_qty), 0).label(
                    "total_variance_qty"
                ),
                func.coalesce(
                    func.sum(ReconciliationRecord.variance_qty * Item.unit_price_aed), 0
                ).label("total_variance_value_aed"),
            )
            .join(Item, ReconciliationRecord.item_id == Item.id)
            .join(DeliveryOrder, ReconciliationRecord.delivery_order_id == DeliveryOrder.id)
            .where(ReconciliationRecord.organization_id == organization_id)
        )
        if project_id is not None:
            stmt = stmt.where(ReconciliationRecord.project_id == project_id)
        if date_from is not None:
            stmt = stmt.where(DeliveryOrder.dispatch_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(DeliveryOrder.dispatch_date <= date_to)

        stmt = stmt.group_by(ReconciliationRecord.reconciliation_status)
        return [dict(r) for r in self.db.execute(stmt).mappings().all()]
