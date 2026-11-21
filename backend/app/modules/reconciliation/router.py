"""FastAPI router definitions for /reconciliation endpoints."""

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
from app.modules.reconciliation.controller import ReconciliationController
from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.schemas import (
    FlagDiscrepancyRequest,
    LossWriteOffRequest,
    ReconciliationDetailResponse,
    ReconciliationRecordResponse,
    ResolveDiscrepancyRequest,
)
from app.modules.reconciliation.service import ReconciliationService
from app.shared.enums import ReconciliationStatus, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def get_controller(db: DbSession) -> ReconciliationController:
    return ReconciliationController(ReconciliationService(ReconciliationRepository(db)))


@router.get("", response_model=PaginatedResponse[ReconciliationRecordResponse])
def list_reconciliation_records(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    project_id: UUID | None = Query(default=None),
    delivery_order_id: UUID | None = Query(default=None),
    item_id: UUID | None = Query(default=None),
    reconciliation_status: ReconciliationStatus | None = Query(default=None),
    only_with_variance: bool | None = Query(default=None),
    controller: ReconciliationController = Depends(get_controller),
) -> PaginatedResponse[ReconciliationRecordResponse]:
    return controller.list_records(
        current_user,
        pagination,
        project_id=project_id,
        delivery_order_id=delivery_order_id,
        item_id=item_id,
        status=reconciliation_status,
        only_with_variance=only_with_variance,
    )


@router.get("/{recon_id}", response_model=APIResponse[ReconciliationDetailResponse])
def get_reconciliation_record(
    recon_id: UUID,
    current_user: CurrentUserDep,
    controller: ReconciliationController = Depends(get_controller),
) -> APIResponse[ReconciliationDetailResponse]:
    return controller.get_detail(current_user, recon_id)


@router.post("/{recon_id}/flag-discrepancy", response_model=APIResponse[ReconciliationRecordResponse])
def flag_discrepancy(
    recon_id: UUID,
    payload: FlagDiscrepancyRequest,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: ReconciliationController = Depends(get_controller),
) -> APIResponse[ReconciliationRecordResponse]:
    return controller.flag_discrepancy(current_user, recon_id, payload)


@router.post("/{recon_id}/write-off", response_model=APIResponse[ReconciliationRecordResponse])
def write_off_loss(
    recon_id: UUID,
    payload: LossWriteOffRequest,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: ReconciliationController = Depends(get_controller),
) -> APIResponse[ReconciliationRecordResponse]:
    return controller.write_off_loss(current_user, recon_id, payload)


@router.post("/{recon_id}/resolve", response_model=APIResponse[ReconciliationRecordResponse])
def resolve_discrepancy(
    recon_id: UUID,
    payload: ResolveDiscrepancyRequest,
    current_user: CurrentUserContext = Depends(require_roles(UserRole.ADMIN)),
    controller: ReconciliationController = Depends(get_controller),
) -> APIResponse[ReconciliationRecordResponse]:
    return controller.resolve_discrepancy(current_user, recon_id, payload)
