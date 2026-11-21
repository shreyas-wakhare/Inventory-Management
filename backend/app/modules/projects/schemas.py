"""Pydantic v2 request/response schemas for projects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.enums import ProjectStatus


class ProjectCreate(BaseModel):
    project_code: str = Field(..., min_length=2, max_length=64)
    project_name: str = Field(..., min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> ProjectCreate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date.")
        return self


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=255)
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_code: str
    project_name: str
    location: str | None
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime


class ProjectSummaryResponse(ProjectResponse):
    deployed_units_count: int = 0


class ProjectDetailResponse(ProjectSummaryResponse):
    active_delivery_orders_count: int = 0
    open_reconciliations_count: int = 0
    outstanding_variance_qty: Decimal = Decimal("0.000")
