"""HTTP controller layer for pre-aggregated analytics & chart endpoints."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from app.core.dependencies import CurrentUserContext
from app.modules.analytics.schemas import (
    KPISummaryData,
    MovementTrendsData,
    ProjectUtilizationData,
    ReconciliationHealthData,
    StockDistributionData,
)
from app.modules.analytics.service import AnalyticsService
from app.shared.enums import OwnershipSource, ProductType, ProjectStatus
from app.shared.schemas import ChartSeriesResponse


class AnalyticsController:
    """Wraps analytics service outputs in ChartSeriesResponse envelopes."""

    def __init__(self, service: AnalyticsService) -> None:
        self.service = service

    def get_kpi_summary(
        self,
        ctx: CurrentUserContext,
        *,
        ownership_source: OwnershipSource | None = None,
    ) -> ChartSeriesResponse[KPISummaryData]:
        data = self.service.get_kpi_summary(ctx, ownership_source=ownership_source)
        return ChartSeriesResponse(
            data=data,
            filters_applied={
                "ownership_source": ownership_source.value if ownership_source else None
            },
        )

    def get_stock_distribution(
        self,
        ctx: CurrentUserContext,
        *,
        group_by: Literal["category", "product_type", "ownership_source"] = "category",
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> ChartSeriesResponse[StockDistributionData]:
        data = self.service.get_stock_distribution(
            ctx,
            group_by=group_by,
            product_type=product_type,
            ownership_source=ownership_source,
        )
        return ChartSeriesResponse(
            data=data,
            filters_applied={
                "group_by": group_by,
                "product_type": product_type.value if product_type else None,
                "ownership_source": ownership_source.value if ownership_source else None,
            },
        )

    def get_project_utilization(
        self,
        ctx: CurrentUserContext,
        *,
        status: ProjectStatus | None = ProjectStatus.ACTIVE,
        limit: int = 10,
        sort_by: Literal["deployed_value_aed", "deployed_units", "outstanding_qty"] = "deployed_value_aed",
    ) -> ChartSeriesResponse[ProjectUtilizationData]:
        data = self.service.get_project_utilization(
            ctx,
            status=status,
            limit=limit,
            sort_by=sort_by,
        )
        return ChartSeriesResponse(
            data=data,
            filters_applied={
                "status": status.value if status else None,
                "limit": limit,
                "sort_by": sort_by,
            },
        )

    def get_movement_trends(
        self,
        ctx: CurrentUserContext,
        *,
        granularity: Literal["day", "week"] = "day",
        date_from: date | None = None,
        date_to: date | None = None,
        product_type: ProductType | None = None,
        project_id: UUID | None = None,
    ) -> ChartSeriesResponse[MovementTrendsData]:
        data, resolved_from, resolved_to = self.service.get_movement_trends(
            ctx,
            granularity=granularity,
            date_from=date_from,
            date_to=date_to,
            product_type=product_type,
            project_id=project_id,
        )
        return ChartSeriesResponse(
            data=data,
            filters_applied={
                "granularity": granularity,
                "date_from": resolved_from.isoformat(),
                "date_to": resolved_to.isoformat(),
                "product_type": product_type.value if product_type else None,
                "project_id": str(project_id) if project_id else None,
            },
        )

    def get_reconciliation_health(
        self,
        ctx: CurrentUserContext,
        *,
        project_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> ChartSeriesResponse[ReconciliationHealthData]:
        data = self.service.get_reconciliation_health(
            ctx,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )
        return ChartSeriesResponse(
            data=data,
            filters_applied={
                "project_id": str(project_id) if project_id else None,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        )
