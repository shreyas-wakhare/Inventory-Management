"""Pydantic v2 schemas for the immutable stock_movements audit ledger."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class StockMovementResponse(BaseModel):
    id: UUID
    organization_id: UUID
    item_id: UUID
    item_code: str
    item_description: str
    equipment_unit_id: UUID | None
    serial_number: str | None = None
    project_id: UUID | None
    project_code: str | None = None
    ownership_source: str
    movement_type: str
    from_bucket: str | None
    to_bucket: str | None
    quantity: Decimal
    reference_type: str | None
    reference_number: str | None
    notes: str | None
    created_by: UUID
    created_by_name: str
    created_at: datetime
