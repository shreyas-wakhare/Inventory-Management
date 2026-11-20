"""Shared FastAPI dependencies (database session, pagination, auth guards)."""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


class PaginationParams(BaseModel):
    """Standard pagination parameters for list endpoints."""

    page: int = 1
    page_size: int = 25


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=25, ge=1, le=200, description="Number of items per page"),
) -> PaginationParams:
    """Resolve and validate pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]

