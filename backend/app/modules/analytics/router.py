"""FastAPI router definitions for /analytics dashboard KPI & chart endpoints."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUserDep, DbSession
from app.modules.analytics.controller import AnalyticsController
from app.modules.analytics.repository import AnalyticsRepository
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

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_controller(db: DbSession) -> AnalyticsController:
    return AnalyticsController(AnalyticsService(AnalyticsRepository(db)))


@router.get("/kpi-summary", response_model=ChartSeriesResponse[KPISummaryData])
def kpi_summary(
    current_user: CurrentUserDep,
    ownership_source: OwnershipSource | None = Query(default=None),
    controller: AnalyticsController = Depends(get_controller),
) -> ChartSeriesResponse[KPISummaryData]:
    return controller.get_kpi_summary(current_user, ownership_source=ownership_source)


@router.get("/stock-distribution", response_model=ChartSeriesResponse[StockDistributionData])
def stock_distribution(
    current_user: CurrentUserDep,
    group_by: Literal["category", "product_type", "ownership_source"] = Query(default="category"),
    product_type: ProductType | None = Query(default=None),
    ownership_source: OwnershipSource | None = Query(default=None),
    controller: AnalyticsController = Depends(get_controller),
) -> ChartSeriesResponse[StockDistributionData]:
    return controller.get_stock_distribution(
        current_user,
        group_by=group_by,
        product_type=product_type,
        ownership_source=ownership_source,
    )


@router.get("/project-utilization", response_model=ChartSeriesResponse[ProjectUtilizationData])
def project_utilization(
    current_user: CurrentUserDep,
    project_status: ProjectStatus | None = Query(default=ProjectStatus.ACTIVE, alias="status"),
    limit: int = Query(default=10, ge=1, le=50),
    sort_by: Literal["deployed_value_aed", "deployed_units", "outstanding_qty"] = Query(
        default="deployed_value_aed"
    ),
    controller: AnalyticsController = Depends(get_controller),
) -> ChartSeriesResponse[ProjectUtilizationData]:
    return controller.get_project_utilization(
        current_user,
        status=project_status,
        limit=limit,
        sort_by=sort_by,
    )


@router.get("/movement-trends", response_model=ChartSeriesResponse[MovementTrendsData])
def movement_trends(
    current_user: CurrentUserDep,
    granularity: Literal["day", "week"] = Query(default="day"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    controller: AnalyticsController = Depends(get_controller),
) -> ChartSeriesResponse[MovementTrendsData]:
    return controller.get_movement_trends(
        current_user,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        product_type=product_type,
        project_id=project_id,
    )


@router.get("/reconciliation-health", response_model=ChartSeriesResponse[ReconciliationHealthData])
def reconciliation_health(
    current_user: CurrentUserDep,
    project_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    controller: AnalyticsController = Depends(get_controller),
) -> ChartSeriesResponse[ReconciliationHealthData]:
    return controller.get_reconciliation_health(
        current_user,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
    )
