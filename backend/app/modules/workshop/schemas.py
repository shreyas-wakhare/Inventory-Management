"""Pydantic v2 schemas for Workshop Replenishment workflows."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import OwnershipSource


class ReplenishmentCompleteRequest(BaseModel):
    item_id: UUID
    equipment_unit_id: UUID | None = None
    ownership_source: OwnershipSource = OwnershipSource.SER
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    workshop_ticket_ref: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=500)


class ReplenishmentCompleteResponse(BaseModel):
    item_id: UUID
    item_code: str
    equipment_unit_id: UUID | None
    serial_number: str | None = None
    ownership_source: OwnershipSource
    released_qty: Decimal
    remaining_replenishment_qty: Decimal
    new_available_qty: Decimal
    movement_id: UUID
