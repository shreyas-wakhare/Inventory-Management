"""FastAPI router definitions for /stock-movements audit ledger endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUserDep, DbSession, PaginationDep
from app.modules.stock_movements.controller import StockMovementController
from app.modules.stock_movements.repository import StockMovementRepository
from app.modules.stock_movements.schemas import StockMovementResponse
from app.modules.stock_movements.service import StockMovementService
from app.shared.enums import MovementType, OwnershipSource
from app.shared.schemas import PaginatedResponse

router = APIRouter(prefix="/stock-movements", tags=["stock-movements"])


def get_controller(db: DbSession) -> StockMovementController:
    return StockMovementController(StockMovementService(StockMovementRepository(db)))


@router.get("", response_model=PaginatedResponse[StockMovementResponse])
def list_stock_movements(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    item_id: UUID | None = Query(default=None),
    equipment_unit_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    ownership_source: OwnershipSource | None = Query(default=None),
    movement_type: MovementType | None = Query(default=None),
    reference_number: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    controller: StockMovementController = Depends(get_controller),
) -> PaginatedResponse[StockMovementResponse]:
    return controller.list_movements(
        current_user,
        pagination,
        item_id=item_id,
        equipment_unit_id=equipment_unit_id,
        project_id=project_id,
        ownership_source=ownership_source,
        movement_type=movement_type,
        reference_number=reference_number,
        date_from=date_from,
        date_to=date_to,
    )
