"""HTTP controller layer for stock balances endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.stock_balances.schemas import (
    CategoryStockSummaryResponse,
    OpeningStockCreate,
    StockAdjustmentCreate,
    StockBalanceResponse,
)
from app.modules.stock_balances.service import StockBalanceService
from app.shared.enums import OwnershipSource, ProductType
from app.shared.schemas import APIResponse, PaginatedResponse


class StockBalanceController:
    """Coordinates HTTP envelopes for stock balances."""

    def __init__(self, service: StockBalanceService) -> None:
        self.service = service

    def list_balances(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        item_id: UUID | None = None,
        product_type: ProductType | None = None,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
        has_replenishment: bool | None = None,
        has_damaged: bool | None = None,
        low_stock_only: bool | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[StockBalanceResponse]:
        return self.service.list_balances(
            ctx,
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

    def summarize_by_category(
        self,
        ctx: CurrentUserContext,
        *,
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> APIResponse[list[CategoryStockSummaryResponse]]:
        return APIResponse(
            data=self.service.summarize_by_category(
                ctx,
                product_type=product_type,
                ownership_source=ownership_source,
            )
        )

    def record_opening_stock(
        self,
        ctx: CurrentUserContext,
        payload: OpeningStockCreate,
    ) -> APIResponse[StockBalanceResponse]:
        return APIResponse(
            data=self.service.record_opening_stock(ctx, payload),
            message="opening_stock_recorded",
        )

    def record_adjustment(
        self,
        ctx: CurrentUserContext,
        payload: StockAdjustmentCreate,
    ) -> APIResponse[StockBalanceResponse]:
        return APIResponse(
            data=self.service.record_adjustment(ctx, payload),
            message="adjustment_recorded",
        )
