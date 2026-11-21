"""Business logic service for serialized equipment units."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    DuplicateBusinessKeyError,
    NotFoundError,
    ValidationDomainError,
)
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.equipment_units.repository import EquipmentUnitRepository
from app.modules.equipment_units.schemas import (
    EquipmentUnitCreate,
    EquipmentUnitMovementResponse,
    EquipmentUnitResponse,
    EquipmentUnitUpdate,
)
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_movements.models import StockMovement
from app.shared.enums import (
    ConditionStatus,
    EquipmentUnitStatus,
    MovementType,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta


def _to_unit_response(
    unit: EquipmentUnit,
    item: Item,
    project: Project | None,
) -> EquipmentUnitResponse:
    return EquipmentUnitResponse(
        id=unit.id,
        organization_id=unit.organization_id,
        item_id=unit.item_id,
        serial_number=unit.serial_number,
        status=EquipmentUnitStatus(unit.status),
        condition_status=ConditionStatus(unit.condition_status),
        current_project_id=unit.current_project_id,
        notes=unit.notes,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
        item_code=item.item_code,
        item_description=item.description,
        category=item.category,
        sub_category=item.sub_category,
        unit_price_aed=item.unit_price_aed,
        current_project_code=project.project_code if project else None,
        current_project_name=project.project_name if project else None,
    )


class EquipmentUnitService:
    """Manages serialized physical units, onboarding, condition updates, and movement history."""

    def __init__(self, repository: EquipmentUnitRepository) -> None:
        self.repository = repository

    def list_units(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        item_id: UUID | None = None,
        status: EquipmentUnitStatus | None = None,
        condition_status: ConditionStatus | None = None,
        current_project_id: UUID | None = None,
        category: str | None = None,
    ) -> PaginatedResponse[EquipmentUnitResponse]:
        rows, total = self.repository.list_units(
            ctx.organization_id,
            search=search,
            item_id=item_id,
            status=status,
            condition_status=condition_status,
            current_project_id=current_project_id,
            category=category,
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

    def create_unit(
        self,
        ctx: CurrentUserContext,
        payload: EquipmentUnitCreate,
    ) -> EquipmentUnitResponse:
        serial = payload.serial_number.strip()
        item = self.repository.get_item_for_org(ctx.organization_id, payload.item_id)
        if item is None:
            raise NotFoundError("Catalog item not found.", details={"item_id": str(payload.item_id)})
        if not item.is_serialized:
            raise ValidationDomainError(
                "Equipment units can only be created for serialized ASSET items.",
                details={"item_code": item.item_code, "product_type": item.product_type},
            )
        if self.repository.get_by_serial(ctx.organization_id, serial) is not None:
            raise DuplicateBusinessKeyError(
                f"Equipment unit serial '{serial}' already exists in this organization.",
                details={"serial_number": serial},
            )

        unit = EquipmentUnit(
            organization_id=ctx.organization_id,
            item_id=item.id,
            serial_number=serial,
            status=EquipmentUnitStatus.AVAILABLE.value,
            condition_status=payload.condition_status.value,
            current_project_id=None,
            notes=payload.notes.strip() if payload.notes else None,
        )
        self.repository.db.add(unit)
        self.repository.db.flush()

        balance = self.repository.get_balance_for_update(
            ctx.organization_id,
            item.id,
            payload.ownership_source.value,
        )
        if balance is None:
            balance = StockBalance(
                organization_id=ctx.organization_id,
                item_id=item.id,
                ownership_source=payload.ownership_source.value,
                available_qty=Decimal("1"),
                in_use_qty=Decimal("0"),
                replenishment_qty=Decimal("0"),
                damaged_qty=Decimal("0"),
            )
            self.repository.db.add(balance)
        else:
            balance.available_qty += Decimal("1")

        self.repository.db.add(
            StockMovement(
                organization_id=ctx.organization_id,
                item_id=item.id,
                equipment_unit_id=unit.id,
                project_id=None,
                ownership_source=payload.ownership_source.value,
                movement_type=MovementType.OPENING_STOCK.value,
                from_bucket=StockBucket.EXTERNAL.value,
                to_bucket=StockBucket.AVAILABLE.value,
                quantity=Decimal("1"),
                reference_type=ReferenceType.OPENING_BALANCE.value,
                reference_number=serial,
                notes=unit.notes or "New serialized equipment unit onboarded",
                created_by=ctx.user_id,
            )
        )
        self.repository.db.commit()
        self.repository.db.refresh(unit)
        return _to_unit_response(unit, item, None)

    def get_unit(self, ctx: CurrentUserContext, unit_id: UUID) -> EquipmentUnitResponse:
        row = self.repository.get_unit_joined(ctx.organization_id, unit_id)
        if row is None:
            raise NotFoundError(
                "Equipment unit not found.",
                details={"equipment_unit_id": str(unit_id)},
            )
        return _to_unit_response(*row)

    def update_unit(
        self,
        ctx: CurrentUserContext,
        unit_id: UUID,
        payload: EquipmentUnitUpdate,
    ) -> EquipmentUnitResponse:
        row = self.repository.get_unit_joined(ctx.organization_id, unit_id)
        if row is None:
            raise NotFoundError(
                "Equipment unit not found.",
                details={"equipment_unit_id": str(unit_id)},
            )
        unit, item, project = row
        if payload.condition_status is not None:
            unit.condition_status = payload.condition_status.value
        if payload.notes is not None:
            unit.notes = payload.notes.strip() or None
        self.repository.db.commit()
        self.repository.db.refresh(unit)
        return _to_unit_response(unit, item, project)

    def list_unit_movements(
        self,
        ctx: CurrentUserContext,
        unit_id: UUID,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EquipmentUnitMovementResponse]:
        if self.repository.get_by_id(ctx.organization_id, unit_id) is None:
            raise NotFoundError(
                "Equipment unit not found.",
                details={"equipment_unit_id": str(unit_id)},
            )
        rows, total = self.repository.list_unit_movements(
            ctx.organization_id,
            unit_id,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items = [
            EquipmentUnitMovementResponse(
                id=mv.id,
                movement_type=mv.movement_type,
                from_bucket=mv.from_bucket,
                to_bucket=mv.to_bucket,
                quantity=mv.quantity,
                ownership_source=mv.ownership_source,
                project_id=mv.project_id,
                project_code=prj.project_code if prj else None,
                reference_type=mv.reference_type,
                reference_number=mv.reference_number,
                notes=mv.notes,
                created_by=mv.created_by,
                created_by_name=usr.full_name,
                created_at=mv.created_at,
            )
            for mv, prj, usr in rows
        ]
        return PaginatedResponse(
            items=items,
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )
