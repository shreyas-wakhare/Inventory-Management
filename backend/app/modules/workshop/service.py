"""Business & transaction service layer for Workshop Replenishment (SDD-2 Section 5.3)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    InsufficientStockError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationDomainError,
)
from app.modules.equipment_units.schemas import EquipmentUnitResponse
from app.modules.equipment_units.service import _to_unit_response
from app.modules.stock_balances.schemas import StockBalanceResponse
from app.modules.stock_balances.service import _to_balance_response
from app.modules.stock_movements.models import StockMovement
from app.modules.workshop.repository import WorkshopRepository
from app.modules.workshop.schemas import (
    ReplenishmentCompleteRequest,
    ReplenishmentCompleteResponse,
)
from app.shared.enums import (
    ConditionStatus,
    EquipmentUnitStatus,
    MovementType,
    OwnershipSource,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta


class WorkshopService:
    """Manages workshop servicing queues and atomic REPLENISHMENT -> AVAILABLE releases."""

    def __init__(self, repository: WorkshopRepository) -> None:
        self.repository = repository

    def list_replenishment_units(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        item_id: UUID | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[EquipmentUnitResponse]:
        rows, total = self.repository.list_replenishment_units(
            ctx.organization_id,
            item_id=item_id,
            category=category,
            search=search,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse(
            items=[_to_unit_response(u, it, prj) for u, it, prj in rows],
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def list_replenishment_balances(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> PaginatedResponse[StockBalanceResponse]:
        rows, total = self.repository.list_replenishment_balances(
            ctx.organization_id,
            category=category,
            ownership_source=ownership_source,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse(
            items=[_to_balance_response(bal, it) for bal, it in rows],
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def complete_replenishment(
        self,
        ctx: CurrentUserContext,
        payload: ReplenishmentCompleteRequest,
    ) -> ReplenishmentCompleteResponse:
        item = self.repository.get_item_for_org(ctx.organization_id, payload.item_id)
        if item is None:
            raise NotFoundError("Item not found.", details={"item_id": str(payload.item_id)})

        if item.is_serialized:
            if payload.equipment_unit_id is None:
                raise ValidationDomainError(
                    "equipment_unit_id is required to complete replenishment for a serialized ASSET."
                )
            if payload.quantity != Decimal("1"):
                raise ValidationDomainError(
                    "Serialized ASSET replenishment release quantity must equal 1."
                )
        elif payload.equipment_unit_id is not None:
            raise ValidationDomainError(
                "equipment_unit_id must not be specified for bulk ACCESSORY replenishment."
            )

        unit = None
        if payload.equipment_unit_id is not None:
            unit = self.repository.get_unit_for_update(
                ctx.organization_id,
                payload.equipment_unit_id,
            )
            if unit is None or unit.item_id != item.id:
                raise NotFoundError("Equipment unit not found for this item.")
            if unit.status != EquipmentUnitStatus.REPLENISHMENT.value:
                raise InvalidStateTransitionError(
                    f"Equipment unit '{unit.serial_number}' is currently '{unit.status}', not 'REPLENISHMENT'.",
                    details={"serial_number": unit.serial_number, "current_status": unit.status},
                )

        balance = self.repository.get_balance_for_update(
            ctx.organization_id,
            item.id,
            payload.ownership_source.value,
        )
        if balance is None or balance.replenishment_qty < payload.quantity:
            raise InsufficientStockError(
                "Insufficient quantity in REPLENISHMENT bucket to release.",
                details={
                    "replenishment_qty": str(balance.replenishment_qty if balance else Decimal("0")),
                    "requested_qty": str(payload.quantity),
                },
            )

        if unit is not None:
            unit.status = EquipmentUnitStatus.AVAILABLE.value
            unit.condition_status = ConditionStatus.GOOD.value
            if payload.notes:
                unit.notes = payload.notes.strip()

        balance.replenishment_qty -= payload.quantity
        balance.available_qty += payload.quantity

        movement = StockMovement(
            organization_id=ctx.organization_id,
            item_id=item.id,
            equipment_unit_id=unit.id if unit else None,
            project_id=None,
            ownership_source=payload.ownership_source.value,
            movement_type=MovementType.REPLENISHMENT_COMPLETE.value,
            from_bucket=StockBucket.REPLENISHMENT.value,
            to_bucket=StockBucket.AVAILABLE.value,
            quantity=payload.quantity,
            reference_type=ReferenceType.WORKSHOP_TICKET.value,
            reference_number=payload.workshop_ticket_ref,
            notes=payload.notes.strip() if payload.notes else "Workshop servicing completed",
            created_by=ctx.user_id,
        )
        self.repository.db.add(movement)
        self.repository.db.commit()
        self.repository.db.refresh(balance)
        self.repository.db.refresh(movement)

        return ReplenishmentCompleteResponse(
            item_id=item.id,
            item_code=item.item_code,
            equipment_unit_id=unit.id if unit else None,
            serial_number=unit.serial_number if unit else None,
            ownership_source=payload.ownership_source,
            released_qty=payload.quantity,
            remaining_replenishment_qty=balance.replenishment_qty,
            new_available_qty=balance.available_qty,
            movement_id=movement.id,
        )
