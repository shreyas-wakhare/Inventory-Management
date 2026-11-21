"""HTTP controller layer for Workshop Replenishment endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.equipment_units.schemas import EquipmentUnitResponse
from app.modules.stock_balances.schemas import StockBalanceResponse
from app.modules.workshop.schemas import (
    ReplenishmentCompleteRequest,
    ReplenishmentCompleteResponse,
)
from app.modules.workshop.service import WorkshopService
from app.shared.enums import OwnershipSource
from app.shared.schemas import APIResponse, PaginatedResponse


class WorkshopController:
    """Coordinates HTTP envelopes for workshop routes."""

    def __init__(self, service: WorkshopService) -> None:
        self.service = service

    def list_replenishment_units(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        item_id: UUID | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[EquipmentUnitResponse]:
        return self.service.list_replenishment_units(
            ctx,
            pagination,
            item_id=item_id,
            category=category,
            search=search,
        )

    def list_replenishment_balances(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> PaginatedResponse[StockBalanceResponse]:
        return self.service.list_replenishment_balances(
            ctx,
            pagination,
            category=category,
            ownership_source=ownership_source,
        )

    def complete_replenishment(
        self,
        ctx: CurrentUserContext,
        payload: ReplenishmentCompleteRequest,
    ) -> APIResponse[ReplenishmentCompleteResponse]:
        return APIResponse(
            data=self.service.complete_replenishment(ctx, payload),
            message="replenishment_completed",
        )
