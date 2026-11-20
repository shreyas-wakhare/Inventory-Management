"""Shared Pydantic v2 response envelopes and common DTOs."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Application health check response payload."""

    status: str
    service: str
    environment: str


class APIResponse(BaseModel, Generic[T]):
    """Standard single-resource API response wrapper."""

    data: T
    message: str = "ok"


class PaginationMeta(BaseModel):
    """Pagination metadata returned with list responses."""

    page: int
    page_size: int
    total: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated collection response wrapper."""

    items: list[T]
    meta: PaginationMeta

