"""Pydantic v2 request/response schemas for incoming Collection Orders (CO)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import CollectionOrderStatus, OwnershipSource, PostReturnBucket


class CollectionOrderLineCreate(BaseModel):
    delivery_order_line_id: UUID | None = None
    item_id: UUID
    equipment_unit_id: UUID | None = None
    ownership_source: OwnershipSource = OwnershipSource.SER
    returned_qty: Decimal = Field(..., gt=0)
    post_return_bucket: PostReturnBucket
    condition_notes: str | None = None


class CollectionOrderCreate(BaseModel):
    co_number: str = Field(..., min_length=2, max_length=64)
    project_id: UUID
    delivery_order_id: UUID | None = None
    collection_date: date | None = None
    remarks: str | None = None
    lines: list[CollectionOrderLineCreate] = Field(..., min_length=1)


class CollectionOrderUpdate(BaseModel):
    collection_date: date | None = None
    remarks: str | None = None
    lines: list[CollectionOrderLineCreate] | None = None


class CollectionOrderReceiveRequest(BaseModel):
    collection_date: date | None = None
    remarks: str | None = None


class CollectionCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class CollectionOrderLineResponse(BaseModel):
    id: UUID
    collection_order_id: UUID
    delivery_order_line_id: UUID | None
    item_id: UUID
    item_code: str
    item_description: str
    uom: str
    equipment_unit_id: UUID | None
    serial_number: str | None = None
    ownership_source: OwnershipSource
    returned_qty: Decimal
    post_return_bucket: PostReturnBucket
    condition_notes: str | None
    created_at: datetime


class CollectionOrderResponse(BaseModel):
    id: UUID
    organization_id: UUID
    co_number: str
    project_id: UUID
    project_code: str
    project_name: str
    delivery_order_id: UUID | None
    do_number: str | None = None
    collection_date: date
    status: CollectionOrderStatus
    remarks: str | None
    created_by: UUID
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class CollectionOrderSummaryResponse(CollectionOrderResponse):
    line_count: int = 0
    total_returned_qty: Decimal = Decimal("0.000")


class CollectionOrderDetailResponse(CollectionOrderResponse):
    lines: list[CollectionOrderLineResponse] = Field(default_factory=list)
