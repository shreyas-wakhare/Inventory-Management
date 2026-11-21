"""Pydantic v2 schemas for real-time stock balances, category rollups, opening stock, and adjustments."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import OwnershipSource, ProductType


class StockBalanceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    item_id: UUID
    item_code: str
    item_description: str
    uom: str
    product_type: ProductType
    category: str
    sub_category: str | None
    unit_price_aed: Decimal
    ownership_source: OwnershipSource
    available_qty: Decimal
    in_use_qty: Decimal
    replenishment_qty: Decimal
    damaged_qty: Decimal
    total_qty: Decimal
    available_value_aed: Decimal
    in_use_value_aed: Decimal
    total_value_aed: Decimal
    updated_at: datetime


class CategoryStockSummaryResponse(BaseModel):
    category: str
    item_count: int
    available_qty: Decimal
    in_use_qty: Decimal
    replenishment_qty: Decimal
    damaged_qty: Decimal
    total_qty: Decimal
    available_value_aed: Decimal
    in_use_value_aed: Decimal
    total_value_aed: Decimal


class OpeningStockCreate(BaseModel):
    item_id: UUID
    ownership_source: OwnershipSource = OwnershipSource.SER
    quantity: Decimal = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=500)


class StockAdjustmentCreate(BaseModel):
    item_id: UUID
    equipment_unit_id: UUID | None = None
    ownership_source: OwnershipSource = OwnershipSource.SER
    from_bucket: Literal["AVAILABLE", "REPLENISHMENT", "DAMAGED"]
    to_bucket: Literal["AVAILABLE", "REPLENISHMENT", "DAMAGED", "RETIRED"]
    quantity: Decimal = Field(..., gt=0)
    notes: str = Field(..., min_length=5, max_length=500)
