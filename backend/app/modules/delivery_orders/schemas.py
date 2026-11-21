"""Pydantic v2 request/response schemas for outgoing Delivery Orders (DO)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import DeliveryOrderStatus, OwnershipSource


class DeliveryOrderLineCreate(BaseModel):
    item_id: UUID
    equipment_unit_id: UUID | None = None
    ownership_source: OwnershipSource = OwnershipSource.SER
    dispatched_qty: Decimal = Field(..., gt=0)


class DeliveryOrderCreate(BaseModel):
    do_number: str = Field(..., min_length=2, max_length=64)
    project_id: UUID
    dispatch_date: date | None = None
    remarks: str | None = None
    lines: list[DeliveryOrderLineCreate] = Field(..., min_length=1)


class DeliveryOrderUpdate(BaseModel):
    dispatch_date: date | None = None
    remarks: str | None = None
    lines: list[DeliveryOrderLineCreate] | None = None


class DeliveryOrderDispatchRequest(BaseModel):
    dispatch_date: date | None = None
    remarks: str | None = None


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class DeliveryOrderLineResponse(BaseModel):
    id: UUID
    delivery_order_id: UUID
    item_id: UUID
    item_code: str
    item_description: str
    uom: str
    equipment_unit_id: UUID | None
    serial_number: str | None = None
    ownership_source: OwnershipSource
    dispatched_qty: Decimal
    returned_qty: Decimal
    lost_qty: Decimal
    remaining_qty: Decimal
    created_at: datetime


class DeliveryOrderResponse(BaseModel):
    id: UUID
    organization_id: UUID
    do_number: str
    project_id: UUID
    project_code: str
    project_name: str
    dispatch_date: date
    status: DeliveryOrderStatus
    remarks: str | None
    created_by: UUID
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class DeliveryOrderSummaryResponse(DeliveryOrderResponse):
    line_count: int = 0
    total_dispatched_qty: Decimal = Decimal("0.000")
    total_returned_qty: Decimal = Decimal("0.000")
    total_outstanding_qty: Decimal = Decimal("0.000")


class DeliveryOrderDetailResponse(DeliveryOrderResponse):
    lines: list[DeliveryOrderLineResponse] = Field(default_factory=list)
