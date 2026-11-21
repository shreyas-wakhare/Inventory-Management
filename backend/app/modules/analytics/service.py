"""Business logic service for pre-aggregated frontend KPI and chart analytics."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from app.core.dependencies import CurrentUserContext
from app.core.exceptions import ValidationDomainError
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schemas import (
    BucketMetric,
    BucketsKPI,
    CatalogKPI,
    KPISummaryData,
    MovementTrendPoint,
    MovementTrendsData,
    ProjectUtilizationData,
    ProjectUtilizationPoint,
    ReconciliationHealthData,
    ReconciliationStatusPoint,
    StockDistributionData,
    StockDistributionPoint,
)
from app.shared.enums import OwnershipSource, ProductType, ProjectStatus, ReconciliationStatus


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AnalyticsService:
    """Builds chart-ready analytics payloads from server-side PostgreSQL aggregations."""

    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    def get_kpi_summary(
        self,
        ctx: CurrentUserContext,
        *,
        ownership_source: OwnershipSource | None = None,
    ) -> KPISummaryData:
        raw = self.repository.get_kpi_aggregates(
            ctx.organization_id,
            ownership_source=ownership_source,
        )
        bal = raw["bal"]
        unit_counts = raw["unit_counts"]

        avail_units = unit_counts.get("AVAILABLE", 0)
        in_use_units = unit_counts.get("IN_USE", 0)
        repl_units = unit_counts.get("REPLENISHMENT", 0)
        dmg_units = unit_counts.get("DAMAGED", 0)

        active_fleet = avail_units + in_use_units + repl_units + dmg_units
        utilization_pct = round((in_use_units / active_fleet) * 100.0, 2) if active_fleet > 0 else 0.0

        return KPISummaryData(
            catalog=CatalogKPI(
                total_items=raw["total_items"],
                asset_skus=raw["asset_skus"],
                accessory_skus=raw["accessory_skus"],
                total_serialized_units=raw["total_units"],
            ),
            buckets=BucketsKPI(
                available=BucketMetric(
                    qty=Decimal(str(bal["avail_qty"])),
                    units=avail_units,
                    value_aed=_money(Decimal(str(bal["avail_val"]))),
                ),
                in_use=BucketMetric(
                    qty=Decimal(str(bal["in_use_qty"])),
                    units=in_use_units,
                    value_aed=_money(Decimal(str(bal["in_use_val"]))),
                ),
                replenishment=BucketMetric(
                    qty=Decimal(str(bal["repl_qty"])),
                    units=repl_units,
                    value_aed=_money(Decimal(str(bal["repl_val"]))),
                ),
                damaged=BucketMetric(
                    qty=Decimal(str(bal["dmg_qty"])),
                    units=dmg_units,
                    value_aed=_money(Decimal(str(bal["dmg_val"]))),
                ),
            ),
            utilization_rate_pct=utilization_pct,
            active_projects_count=raw["active_projects"],
            open_discrepancies_count=raw["open_discrepancies"],
            total_variance_value_aed=_money(raw["variance_val"]),
        )

    def get_stock_distribution(
        self,
        ctx: CurrentUserContext,
        *,
        group_by: Literal["category", "product_type", "ownership_source"] = "category",
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> StockDistributionData:
        rows = self.repository.get_stock_distribution(
            ctx.organization_id,
            group_by=group_by,
            product_type=product_type,
            ownership_source=ownership_source,
        )
        series = [
            StockDistributionPoint(
                label=str(r["label"]),
                available_qty=Decimal(str(r["available_qty"])),
                in_use_qty=Decimal(str(r["in_use_qty"])),
                replenishment_qty=Decimal(str(r["replenishment_qty"])),
                damaged_qty=Decimal(str(r["damaged_qty"])),
                total_qty=Decimal(str(r["total_qty"])),
                total_value_aed=_money(Decimal(str(r["total_value_aed"]))),
            )
            for r in rows
        ]
        return StockDistributionData(group_by=group_by, series=series)

    def get_project_utilization(
        self,
        ctx: CurrentUserContext,
        *,
        status: ProjectStatus | None = ProjectStatus.ACTIVE,
        limit: int = 10,
        sort_by: Literal["deployed_value_aed", "deployed_units", "outstanding_qty"] = "deployed_value_aed",
    ) -> ProjectUtilizationData:
        rows = self.repository.get_project_utilization(
            ctx.organization_id,
            status=status,
            limit=limit,
            sort_by=sort_by,
        )
        points = [
            ProjectUtilizationPoint(
                project_id=r["project_id"],
                project_code=str(r["project_code"]),
                project_name=str(r["project_name"]),
                deployed_units_count=int(r["deployed_units_count"]),
                bulk_in_use_qty=Decimal(str(r["bulk_in_use_qty"])),
                open_dos_count=int(r["open_dos_count"]),
                outstanding_variance_qty=Decimal(str(r["outstanding_variance_qty"])),
                deployed_value_aed=_money(Decimal(str(r["deployed_value_aed"]))),
            )
            for r in rows
        ]
        return ProjectUtilizationData(projects=points)

    def get_movement_trends(
        self,
        ctx: CurrentUserContext,
        *,
        granularity: Literal["day", "week"] = "day",
        date_from: date | None = None,
        date_to: date | None = None,
        product_type: ProductType | None = None,
        project_id: UUID | None = None,
    ) -> tuple[MovementTrendsData, date, date]:
        resolved_to = date_to or date.today()
        resolved_from = date_from or (resolved_to - timedelta(days=30))
        if resolved_from > resolved_to:
            raise ValidationDomainError("date_from cannot be after date_to.")
        if (resolved_to - resolved_from).days > 366:
            raise ValidationDomainError("Analytics date window cannot exceed 366 days.")

        rows = self.repository.get_movement_trends(
            ctx.organization_id,
            granularity=granularity,
            date_from=resolved_from,
            date_to=resolved_to,
            product_type=product_type,
            project_id=project_id,
        )
        points = [
            MovementTrendPoint(
                period_start=r["period_start"],
                dispatched_qty=Decimal(str(r["dispatched_qty"])),
                returned_available_qty=Decimal(str(r["returned_available_qty"])),
                returned_replenishment_qty=Decimal(str(r["returned_replenishment_qty"])),
                returned_damaged_qty=Decimal(str(r["returned_damaged_qty"])),
                replenishment_completed_qty=Decimal(str(r["replenishment_completed_qty"])),
                loss_write_off_qty=Decimal(str(r["loss_write_off_qty"])),
            )
            for r in rows
        ]
        return (
            MovementTrendsData(granularity=granularity, points=points),
            resolved_from,
            resolved_to,
        )

    def get_reconciliation_health(
        self,
        ctx: CurrentUserContext,
        *,
        project_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> ReconciliationHealthData:
        rows = self.repository.get_reconciliation_health(
            ctx.organization_id,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )
        by_status = {str(r["status"]): r for r in rows}
        ordered_statuses = [
            ReconciliationStatus.EQUALIZED.value,
            ReconciliationStatus.OPEN.value,
            ReconciliationStatus.DISCREPANCY.value,
            ReconciliationStatus.RESOLVED.value,
        ]
        breakdown: list[ReconciliationStatusPoint] = []
        total_records = 0
        equalized_or_resolved = 0

        for st in ordered_statuses:
            r = by_status.get(st)
            cnt = int(r["record_count"]) if r else 0
            total_records += cnt
            if st in {ReconciliationStatus.EQUALIZED.value, ReconciliationStatus.RESOLVED.value}:
                equalized_or_resolved += cnt
            breakdown.append(
                ReconciliationStatusPoint(
                    status=st,
                    record_count=cnt,
                    total_outgoing_qty=Decimal(str(r["total_outgoing_qty"])) if r else Decimal("0"),
                    total_incoming_qty=Decimal(str(r["total_incoming_qty"])) if r else Decimal("0"),
                    total_lost_qty=Decimal(str(r["total_lost_qty"])) if r else Decimal("0"),
                    total_variance_qty=Decimal(str(r["total_variance_qty"])) if r else Decimal("0"),
                    total_variance_value_aed=(
                        _money(Decimal(str(r["total_variance_value_aed"])))
                        if r
                        else Decimal("0.00")
                    ),
                )
            )

        rate = round((equalized_or_resolved / total_records) * 100.0, 2) if total_records > 0 else 100.0
        return ReconciliationHealthData(breakdown=breakdown, equalization_rate_pct=rate)
