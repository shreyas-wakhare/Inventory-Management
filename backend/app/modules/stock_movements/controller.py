"""HTTP controller layer for stock_movements audit ledger endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.stock_movements.schemas import StockMovementResponse
from app.modules.stock_movements.service import StockMovementService
from app.shared.enums import MovementType, OwnershipSource
from app.shared.schemas import PaginatedResponse


class StockMovementController:
    """Coordinates HTTP responses for stock movements."""

    def __init__(self, service: StockMovementService) -> None:
        self.service = service

    def list_movements(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        item_id: UUID | None = None,
        equipment_unit_id: UUID | None = None,
        project_id: UUID | None = None,
        ownership_source: OwnershipSource | None = None,
        movement_type: MovementType | None = None,
        reference_number: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PaginatedResponse[StockMovementResponse]:
        return self.service.list_movements(
            ctx,
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
