"""Pydantic v2 schemas for Next.js KPI cards and pre-aggregated chart series."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CatalogKPI(BaseModel):
    total_items: int
    asset_skus: int
    accessory_skus: int
    total_serialized_units: int


class BucketMetric(BaseModel):
    qty: Decimal
    units: int
    value_aed: Decimal


class BucketsKPI(BaseModel):
    available: BucketMetric
    in_use: BucketMetric
    replenishment: BucketMetric
    damaged: BucketMetric


class KPISummaryData(BaseModel):
    catalog: CatalogKPI
    buckets: BucketsKPI
    utilization_rate_pct: float
    active_projects_count: int
    open_discrepancies_count: int
    total_variance_value_aed: Decimal


class StockDistributionPoint(BaseModel):
    label: str
    available_qty: Decimal
    in_use_qty: Decimal
    replenishment_qty: Decimal
    damaged_qty: Decimal
    total_qty: Decimal
    total_value_aed: Decimal


class StockDistributionData(BaseModel):
    group_by: Literal["category", "product_type", "ownership_source"]
    series: list[StockDistributionPoint]


class ProjectUtilizationPoint(BaseModel):
    project_id: UUID
    project_code: str
    project_name: str
    deployed_units_count: int
    bulk_in_use_qty: Decimal
    open_dos_count: int
    outstanding_variance_qty: Decimal
    deployed_value_aed: Decimal


class ProjectUtilizationData(BaseModel):
    projects: list[ProjectUtilizationPoint]


class MovementTrendPoint(BaseModel):
    period_start: date
    dispatched_qty: Decimal
    returned_available_qty: Decimal
    returned_replenishment_qty: Decimal
    returned_damaged_qty: Decimal
    replenishment_completed_qty: Decimal
    loss_write_off_qty: Decimal


class MovementTrendsData(BaseModel):
    granularity: Literal["day", "week"]
    points: list[MovementTrendPoint]


class ReconciliationStatusPoint(BaseModel):
    status: str
    record_count: int
    total_outgoing_qty: Decimal
    total_incoming_qty: Decimal
    total_lost_qty: Decimal
    total_variance_qty: Decimal
    total_variance_value_aed: Decimal


class ReconciliationHealthData(BaseModel):
    breakdown: list[ReconciliationStatusPoint]
    equalization_rate_pct: float
