"""Business logic service for querying the immutable stock_movements audit ledger."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.stock_movements.repository import StockMovementRepository
from app.modules.stock_movements.schemas import StockMovementResponse
from app.shared.enums import MovementType, OwnershipSource
from app.shared.schemas import PaginatedResponse, build_pagination_meta


class StockMovementService:
    """Provides tenant-scoped audit trail listing and filtering."""

    def __init__(self, repository: StockMovementRepository) -> None:
        self.repository = repository

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
        rows, total = self.repository.list_movements(
            ctx.organization_id,
            item_id=item_id,
            equipment_unit_id=equipment_unit_id,
            project_id=project_id,
            ownership_source=ownership_source,
            movement_type=movement_type,
            reference_number=reference_number,
            date_from=date_from,
            date_to=date_to,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items = [
            StockMovementResponse(
                id=mv.id,
                organization_id=mv.organization_id,
                item_id=mv.item_id,
                item_code=item.item_code,
                item_description=item.description,
                equipment_unit_id=mv.equipment_unit_id,
                serial_number=unit.serial_number if unit else None,
                project_id=mv.project_id,
                project_code=prj.project_code if prj else None,
                ownership_source=mv.ownership_source,
                movement_type=mv.movement_type,
                from_bucket=mv.from_bucket,
                to_bucket=mv.to_bucket,
                quantity=mv.quantity,
                reference_type=mv.reference_type,
                reference_number=mv.reference_number,
                notes=mv.notes,
                created_by=mv.created_by,
                created_by_name=usr.full_name,
                created_at=mv.created_at,
            )
            for mv, item, unit, prj, usr in rows
        ]
        return PaginatedResponse(
            items=items,
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )
