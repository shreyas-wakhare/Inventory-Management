"""Pydantic v2 request/response schemas for the items catalog."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import OwnershipSource, ProductType


class ItemCreate(BaseModel):
    item_code: str = Field(..., min_length=2, max_length=64)
    description: str = Field(..., min_length=2)
    uom: str = Field(default="NOS", min_length=1, max_length=24)
    product_type: ProductType
    category: str = Field(..., min_length=1, max_length=100)
    sub_category: str | None = Field(default=None, max_length=100)
    unit_price_aed: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class ItemUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=2)
    uom: str | None = Field(default=None, min_length=1, max_length=24)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    sub_category: str | None = Field(default=None, max_length=100)
    unit_price_aed: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_active: bool | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    item_code: str
    description: str
    uom: str
    product_type: ProductType
    category: str
    sub_category: str | None
    unit_price_aed: Decimal
    is_serialized: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ItemWithStockResponse(ItemResponse):
    available_qty: Decimal = Decimal("0.000")
    in_use_qty: Decimal = Decimal("0.000")
    replenishment_qty: Decimal = Decimal("0.000")
    damaged_qty: Decimal = Decimal("0.000")
    total_qty: Decimal = Decimal("0.000")
    total_value_aed: Decimal = Decimal("0.00")


class ItemBalanceSlice(BaseModel):
    ownership_source: OwnershipSource
    available_qty: Decimal
    in_use_qty: Decimal
    replenishment_qty: Decimal
    damaged_qty: Decimal
    total_qty: Decimal


class ItemDetailResponse(ItemWithStockResponse):
    balances_by_source: list[ItemBalanceSlice] = Field(default_factory=list)
    unit_status_counts: dict[str, int] = Field(default_factory=dict)


class CategoryFacetResponse(BaseModel):
    category: str
    sub_categories: list[str]
    item_count: int
