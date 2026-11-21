"""HTTP controller layer for serialized equipment units."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.equipment_units.schemas import (
    EquipmentUnitCreate,
    EquipmentUnitMovementResponse,
    EquipmentUnitResponse,
    EquipmentUnitUpdate,
)
from app.modules.equipment_units.service import EquipmentUnitService
from app.shared.enums import ConditionStatus, EquipmentUnitStatus
from app.shared.schemas import APIResponse, PaginatedResponse


class EquipmentUnitController:
    """Coordinates HTTP envelopes for equipment unit routes."""

    def __init__(self, service: EquipmentUnitService) -> None:
        self.service = service

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
        return self.service.list_units(
            ctx,
            pagination,
            search=search,
            item_id=item_id,
            status=status,
            condition_status=condition_status,
            current_project_id=current_project_id,
            category=category,
        )

    def create_unit(
        self,
        ctx: CurrentUserContext,
        payload: EquipmentUnitCreate,
    ) -> APIResponse[EquipmentUnitResponse]:
        return APIResponse(data=self.service.create_unit(ctx, payload), message="created")

    def get_unit(
        self,
        ctx: CurrentUserContext,
        unit_id: UUID,
    ) -> APIResponse[EquipmentUnitResponse]:
        return APIResponse(data=self.service.get_unit(ctx, unit_id))

    def update_unit(
        self,
        ctx: CurrentUserContext,
        unit_id: UUID,
        payload: EquipmentUnitUpdate,
    ) -> APIResponse[EquipmentUnitResponse]:
        return APIResponse(data=self.service.update_unit(ctx, unit_id, payload))

    def list_unit_movements(
        self,
        ctx: CurrentUserContext,
        unit_id: UUID,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EquipmentUnitMovementResponse]:
        return self.service.list_unit_movements(ctx, unit_id, pagination)
