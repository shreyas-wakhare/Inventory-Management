"""FastAPI router definitions for /stock-balances endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUserContext,
    CurrentUserDep,
    DbSession,
    PaginationDep,
    require_roles,
)
from app.modules.stock_balances.controller import StockBalanceController
from app.modules.stock_balances.repository import StockBalanceRepository
from app.modules.stock_balances.schemas import (
    CategoryStockSummaryResponse,
    OpeningStockCreate,
    StockAdjustmentCreate,
    StockBalanceResponse,
)
from app.modules.stock_balances.service import StockBalanceService
from app.shared.enums import OwnershipSource, ProductType, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/stock-balances", tags=["stock-balances"])


def get_controller(db: DbSession) -> StockBalanceController:
    return StockBalanceController(StockBalanceService(StockBalanceRepository(db)))


@router.get("", response_model=PaginatedResponse[StockBalanceResponse])
def list_stock_balances(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    item_id: UUID | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    category: str | None = Query(default=None),
    ownership_source: OwnershipSource | None = Query(default=None),
    has_replenishment: bool | None = Query(default=None),
    has_damaged: bool | None = Query(default=None),
    low_stock_only: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    controller: StockBalanceController = Depends(get_controller),
) -> PaginatedResponse[StockBalanceResponse]:
    return controller.list_balances(
        current_user,
        pagination,
        item_id=item_id,
        product_type=product_type,
        category=category,
        ownership_source=ownership_source,
        has_replenishment=has_replenishment,
        has_damaged=has_damaged,
        low_stock_only=low_stock_only,
        search=search,
    )


@router.get(
    "/summary-by-category",
    response_model=APIResponse[list[CategoryStockSummaryResponse]],
)
def summary_by_category(
    current_user: CurrentUserDep,
    product_type: ProductType | None = Query(default=None),
    ownership_source: OwnershipSource | None = Query(default=None),
    controller: StockBalanceController = Depends(get_controller),
) -> APIResponse[list[CategoryStockSummaryResponse]]:
    return controller.summarize_by_category(
        current_user,
        product_type=product_type,
        ownership_source=ownership_source,
    )


@router.post(
    "/opening-stock",
    response_model=APIResponse[StockBalanceResponse],
    status_code=status.HTTP_201_CREATED,
)
def record_opening_stock(
    payload: OpeningStockCreate,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: StockBalanceController = Depends(get_controller),
) -> APIResponse[StockBalanceResponse]:
    return controller.record_opening_stock(current_user, payload)


@router.post("/adjustments", response_model=APIResponse[StockBalanceResponse])
def record_stock_adjustment(
    payload: StockAdjustmentCreate,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: StockBalanceController = Depends(get_controller),
) -> APIResponse[StockBalanceResponse]:
    return controller.record_adjustment(current_user, payload)
