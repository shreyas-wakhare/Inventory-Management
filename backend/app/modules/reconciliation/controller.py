"""HTTP controller layer for reconciliation endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.reconciliation.schemas import (
    FlagDiscrepancyRequest,
    LossWriteOffRequest,
    ReconciliationDetailResponse,
    ReconciliationRecordResponse,
    ResolveDiscrepancyRequest,
)
from app.modules.reconciliation.service import ReconciliationService
from app.shared.enums import ReconciliationStatus
from app.shared.schemas import APIResponse, PaginatedResponse


class ReconciliationController:
    """Coordinates HTTP envelopes for reconciliation routes."""

    def __init__(self, service: ReconciliationService) -> None:
        self.service = service

    def list_records(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        project_id: UUID | None = None,
        delivery_order_id: UUID | None = None,
        item_id: UUID | None = None,
        status: ReconciliationStatus | None = None,
        only_with_variance: bool | None = None,
    ) -> PaginatedResponse[ReconciliationRecordResponse]:
        return self.service.list_records(
            ctx,
            pagination,
            project_id=project_id,
            delivery_order_id=delivery_order_id,
            item_id=item_id,
            status=status,
            only_with_variance=only_with_variance,
        )

    def get_detail(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
    ) -> APIResponse[ReconciliationDetailResponse]:
        return APIResponse(data=self.service.get_detail(ctx, recon_id))

    def flag_discrepancy(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: FlagDiscrepancyRequest,
    ) -> APIResponse[ReconciliationRecordResponse]:
        return APIResponse(
            data=self.service.flag_discrepancy(ctx, recon_id, payload),
            message="flagged_discrepancy",
        )

    def write_off_loss(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: LossWriteOffRequest,
    ) -> APIResponse[ReconciliationRecordResponse]:
        return APIResponse(
            data=self.service.write_off_loss(ctx, recon_id, payload),
            message="loss_written_off",
        )

    def resolve_discrepancy(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: ResolveDiscrepancyRequest,
    ) -> APIResponse[ReconciliationRecordResponse]:
        return APIResponse(
            data=self.service.resolve_discrepancy(ctx, recon_id, payload),
            message="resolved",
        )
