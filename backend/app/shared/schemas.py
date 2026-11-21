"""Shared Pydantic v2 response envelopes and pagination helpers (SDD-2 Section 4.1)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Application health check response payload."""

    status: str
    service: str
    environment: str
    database: str


class APIResponse(BaseModel, Generic[T]):
    """Standard single-resource API response wrapper."""

    data: T
    message: str = "ok"


class PaginationMeta(BaseModel):
    """Pagination metadata returned with list responses."""

    page: int
    page_size: int
    total: int
    total_pages: int


def build_pagination_meta(*, page: int, page_size: int, total: int) -> PaginationMeta:
    """Compute standardized pagination metadata."""
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated collection response wrapper."""

    items: list[T]
    meta: PaginationMeta


class ChartSeriesResponse(BaseModel, Generic[T]):
    """Standard pre-aggregated analytics/chart payload wrapper for Next.js."""

    data: T
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    filters_applied: dict[str, Any] = Field(default_factory=dict)
