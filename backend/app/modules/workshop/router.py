"""FastAPI router definitions for /workshop endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    CurrentUserContext,
    CurrentUserDep,
    DbSession,
    PaginationDep,
    require_roles,
)
from app.modules.equipment_units.schemas import EquipmentUnitResponse
from app.modules.stock_balances.schemas import StockBalanceResponse
from app.modules.workshop.controller import WorkshopController
from app.modules.workshop.repository import WorkshopRepository
from app.modules.workshop.schemas import (
    ReplenishmentCompleteRequest,
    ReplenishmentCompleteResponse,
)
from app.modules.workshop.service import WorkshopService
from app.shared.enums import OwnershipSource, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/workshop", tags=["workshop"])


def get_controller(db: DbSession) -> WorkshopController:
    return WorkshopController(WorkshopService(WorkshopRepository(db)))


@router.get("/replenishment/units", response_model=PaginatedResponse[EquipmentUnitResponse])
def list_replenishment_units(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    item_id: UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    controller: WorkshopController = Depends(get_controller),
) -> PaginatedResponse[EquipmentUnitResponse]:
    return controller.list_replenishment_units(
        current_user,
        pagination,
        item_id=item_id,
        category=category,
        search=search,
    )


@router.get("/replenishment/balances", response_model=PaginatedResponse[StockBalanceResponse])
def list_replenishment_balances(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    category: str | None = Query(default=None),
    ownership_source: OwnershipSource | None = Query(default=None),
    controller: WorkshopController = Depends(get_controller),
) -> PaginatedResponse[StockBalanceResponse]:
    return controller.list_replenishment_balances(
        current_user,
        pagination,
        category=category,
        ownership_source=ownership_source,
    )


@router.post(
    "/replenishment/complete",
    response_model=APIResponse[ReplenishmentCompleteResponse],
)
def complete_replenishment(
    payload: ReplenishmentCompleteRequest,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.WORKSHOP_LEAD, UserRole.ADMIN)
    ),
    controller: WorkshopController = Depends(get_controller),
) -> APIResponse[ReplenishmentCompleteResponse]:
    return controller.complete_replenishment(current_user, payload)
