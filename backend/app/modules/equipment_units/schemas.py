"""Pydantic v2 request/response schemas for serialized equipment units."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import ConditionStatus, EquipmentUnitStatus, OwnershipSource


class EquipmentUnitCreate(BaseModel):
    item_id: UUID
    serial_number: str = Field(..., min_length=1, max_length=100)
    ownership_source: OwnershipSource = OwnershipSource.SER
    condition_status: ConditionStatus = ConditionStatus.GOOD
    notes: str | None = None


class EquipmentUnitUpdate(BaseModel):
    condition_status: ConditionStatus | None = None
    notes: str | None = None


class EquipmentUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    item_id: UUID
    serial_number: str
    status: EquipmentUnitStatus
    condition_status: ConditionStatus
    current_project_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    item_code: str
    item_description: str
    category: str
    sub_category: str | None = None
    unit_price_aed: Decimal = Decimal("0.00")
    current_project_code: str | None = None
    current_project_name: str | None = None


class EquipmentUnitMovementResponse(BaseModel):
    id: UUID
    movement_type: str
    from_bucket: str | None
    to_bucket: str | None
    quantity: Decimal
    ownership_source: str
    project_id: UUID | None
    project_code: str | None = None
    reference_type: str | None
    reference_number: str | None
    notes: str | None
    created_by: UUID
    created_by_name: str
    created_at: datetime
