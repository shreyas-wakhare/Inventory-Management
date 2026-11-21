"""Pydantic v2 schemas for reconciliation records, loss write-off, and resolution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.stock_movements.schemas import StockMovementResponse
from app.shared.enums import OwnershipSource, ReconciliationStatus


class FlagDiscrepancyRequest(BaseModel):
    notes: str = Field(..., min_length=3, max_length=500)


class LossWriteOffRequest(BaseModel):
    write_off_qty: Decimal = Field(..., gt=0)
    ownership_source: OwnershipSource = OwnershipSource.SER
    notes: str = Field(..., min_length=5, max_length=500)
    resolve_if_zero: bool = True


class ResolveDiscrepancyRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=5, max_length=500)


class ReconciliationRecordResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    project_code: str
    project_name: str
    delivery_order_id: UUID
    do_number: str
    item_id: UUID
    item_code: str
    item_description: str
    uom: str
    equipment_unit_id: UUID | None
    serial_number: str | None = None
    outgoing_qty: Decimal
    incoming_qty: Decimal
    lost_qty: Decimal
    variance_qty: Decimal
    variance_value_aed: Decimal
    reconciliation_status: ReconciliationStatus
    resolved_by: UUID | None
    resolved_by_name: str | None = None
    resolved_at: datetime | None
    updated_at: datetime


class ReconciliationDetailResponse(ReconciliationRecordResponse):
    related_movements: list[StockMovementResponse] = Field(default_factory=list)
