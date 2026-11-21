"""FastAPI router definitions for /equipment-units endpoints."""

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
from app.modules.equipment_units.controller import EquipmentUnitController
from app.modules.equipment_units.repository import EquipmentUnitRepository
from app.modules.equipment_units.schemas import (
    EquipmentUnitCreate,
    EquipmentUnitMovementResponse,
    EquipmentUnitResponse,
    EquipmentUnitUpdate,
)
from app.modules.equipment_units.service import EquipmentUnitService
from app.shared.enums import ConditionStatus, EquipmentUnitStatus, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/equipment-units", tags=["equipment-units"])


def get_controller(db: DbSession) -> EquipmentUnitController:
    return EquipmentUnitController(EquipmentUnitService(EquipmentUnitRepository(db)))


@router.get("", response_model=PaginatedResponse[EquipmentUnitResponse])
def list_equipment_units(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    search: str | None = Query(default=None),
    item_id: UUID | None = Query(default=None),
    unit_status: EquipmentUnitStatus | None = Query(default=None, alias="status"),
    condition_status: ConditionStatus | None = Query(default=None),
    current_project_id: UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    controller: EquipmentUnitController = Depends(get_controller),
) -> PaginatedResponse[EquipmentUnitResponse]:
    return controller.list_units(
        current_user,
        pagination,
        search=search,
        item_id=item_id,
        status=unit_status,
        condition_status=condition_status,
        current_project_id=current_project_id,
        category=category,
    )


@router.post(
    "",
    response_model=APIResponse[EquipmentUnitResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_equipment_unit(
    payload: EquipmentUnitCreate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: EquipmentUnitController = Depends(get_controller),
) -> APIResponse[EquipmentUnitResponse]:
    return controller.create_unit(current_user, payload)


@router.get("/{unit_id}", response_model=APIResponse[EquipmentUnitResponse])
def get_equipment_unit(
    unit_id: UUID,
    current_user: CurrentUserDep,
    controller: EquipmentUnitController = Depends(get_controller),
) -> APIResponse[EquipmentUnitResponse]:
    return controller.get_unit(current_user, unit_id)


@router.patch("/{unit_id}", response_model=APIResponse[EquipmentUnitResponse])
def update_equipment_unit(
    unit_id: UUID,
    payload: EquipmentUnitUpdate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR, UserRole.WORKSHOP_LEAD)
    ),
    controller: EquipmentUnitController = Depends(get_controller),
) -> APIResponse[EquipmentUnitResponse]:
    return controller.update_unit(current_user, unit_id, payload)


@router.get("/{unit_id}/movements", response_model=PaginatedResponse[EquipmentUnitMovementResponse])
def list_equipment_unit_movements(
    unit_id: UUID,
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    controller: EquipmentUnitController = Depends(get_controller),
) -> PaginatedResponse[EquipmentUnitMovementResponse]:
    return controller.list_unit_movements(current_user, unit_id, pagination)
