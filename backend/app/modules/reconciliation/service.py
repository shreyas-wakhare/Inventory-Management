"""Business & transaction service layer for reconciliation, write-offs, and resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    InsufficientStockError,
    InvalidStateTransitionError,
    NotFoundError,
    ReconciliationBoundsError,
    ValidationDomainError,
)
from app.modules.delivery_orders.models import DeliveryOrder
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.schemas import (
    FlagDiscrepancyRequest,
    LossWriteOffRequest,
    ReconciliationDetailResponse,
    ReconciliationRecordResponse,
    ResolveDiscrepancyRequest,
)
from app.modules.stock_movements.models import StockMovement
from app.modules.stock_movements.schemas import StockMovementResponse
from app.modules.users.models import User
from app.shared.enums import (
    DeliveryOrderStatus,
    EquipmentUnitStatus,
    MovementType,
    ReconciliationStatus,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_recon_response(
    rec: ReconciliationRecord,
    project: Project,
    do: DeliveryOrder,
    item: Item,
    unit: EquipmentUnit | None,
    resolver: User | None,
) -> ReconciliationRecordResponse:
    return ReconciliationRecordResponse(
        id=rec.id,
        organization_id=rec.organization_id,
        project_id=rec.project_id,
        project_code=project.project_code,
        project_name=project.project_name,
        delivery_order_id=rec.delivery_order_id,
        do_number=do.do_number,
        item_id=rec.item_id,
        item_code=item.item_code,
        item_description=item.description,
        uom=item.uom,
        equipment_unit_id=rec.equipment_unit_id,
        serial_number=unit.serial_number if unit else None,
        outgoing_qty=rec.outgoing_qty,
        incoming_qty=rec.incoming_qty,
        lost_qty=rec.lost_qty,
        variance_qty=rec.variance_qty,
        variance_value_aed=_money(rec.variance_qty * item.unit_price_aed),
        reconciliation_status=ReconciliationStatus(rec.reconciliation_status),
        resolved_by=rec.resolved_by,
        resolved_by_name=resolver.full_name if resolver else None,
        resolved_at=rec.resolved_at,
        updated_at=rec.updated_at,
    )


class ReconciliationService:
    """Orchestrates reconciliation visibility, discrepancy flagging, write-offs, and resolution."""

    def __init__(self, repository: ReconciliationRepository) -> None:
        self.repository = repository

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
        rows, total = self.repository.list_records(
            ctx.organization_id,
            project_id=project_id,
            delivery_order_id=delivery_order_id,
            item_id=item_id,
            status=status,
            only_with_variance=only_with_variance,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse(
            items=[_to_recon_response(*row) for row in rows],
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def get_detail(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
    ) -> ReconciliationDetailResponse:
        row = self.repository.get_record_joined(ctx.organization_id, recon_id)
        if row is None:
            raise NotFoundError(
                "Reconciliation record not found.",
                details={"reconciliation_id": str(recon_id)},
            )
        rec = row[0]
        base = _to_recon_response(*row)
        mv_rows = self.repository.get_related_movements(
            ctx.organization_id,
            project_id=rec.project_id,
            item_id=rec.item_id,
            equipment_unit_id=rec.equipment_unit_id,
        )
        movements = [
            StockMovementResponse(
                id=mv.id,
                organization_id=mv.organization_id,
                item_id=mv.item_id,
                item_code=it.item_code,
                item_description=it.description,
                equipment_unit_id=mv.equipment_unit_id,
                serial_number=u.serial_number if u else None,
                project_id=mv.project_id,
                project_code=p.project_code if p else None,
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
            for mv, it, u, p, usr in mv_rows
        ]
        return ReconciliationDetailResponse(**base.model_dump(), related_movements=movements)

    def flag_discrepancy(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: FlagDiscrepancyRequest,
    ) -> ReconciliationRecordResponse:
        rec = self.repository.get_for_update(ctx.organization_id, recon_id)
        if rec is None:
            raise NotFoundError(
                "Reconciliation record not found.",
                details={"reconciliation_id": str(recon_id)},
            )
        if rec.variance_qty <= Decimal("0"):
            raise InvalidStateTransitionError(
                "Cannot flag discrepancy when variance_qty is 0.",
                details={"variance_qty": str(rec.variance_qty)},
            )
        if rec.reconciliation_status != ReconciliationStatus.OPEN.value:
            raise InvalidStateTransitionError(
                f"Only OPEN reconciliation records can be flagged as DISCREPANCY (current: {rec.reconciliation_status})."
            )
        rec.reconciliation_status = ReconciliationStatus.DISCREPANCY.value
        self.repository.db.commit()
        joined = self.repository.get_record_joined(ctx.organization_id, recon_id)
        assert joined is not None
        return _to_recon_response(*joined)

    def write_off_loss(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: LossWriteOffRequest,
    ) -> ReconciliationRecordResponse:
        db = self.repository.db
        rec = self.repository.get_for_update(ctx.organization_id, recon_id)
        if rec is None:
            raise NotFoundError(
                "Reconciliation record not found.",
                details={"reconciliation_id": str(recon_id)},
            )
        if payload.write_off_qty > rec.variance_qty:
            raise ReconciliationBoundsError(
                f"write_off_qty ({payload.write_off_qty}) exceeds remaining variance_qty ({rec.variance_qty}).",
                details={
                    "write_off_qty": str(payload.write_off_qty),
                    "variance_qty": str(rec.variance_qty),
                },
            )
        if rec.equipment_unit_id is not None and payload.write_off_qty != Decimal("1"):
            raise ValidationDomainError(
                "Serialized equipment unit write-off quantity must equal 1."
            )

        do_line = self.repository.lock_matching_do_line(
            rec.delivery_order_id,
            rec.item_id,
            rec.equipment_unit_id,
            payload.ownership_source.value,
        )
        balance = self.repository.lock_balance(
            ctx.organization_id,
            rec.item_id,
            payload.ownership_source.value,
        )
        if balance is None or balance.in_use_qty < payload.write_off_qty:
            raise InsufficientStockError(
                "Insufficient IN_USE stock balance to execute loss write-off.",
                details={
                    "in_use_qty": str(balance.in_use_qty if balance else Decimal("0")),
                    "write_off_qty": str(payload.write_off_qty),
                },
            )

        unit = None
        if rec.equipment_unit_id is not None:
            unit = self.repository.lock_unit(ctx.organization_id, rec.equipment_unit_id)
            if unit is not None:
                unit.status = EquipmentUnitStatus.RETIRED.value
                unit.current_project_id = None
                unit.notes = f"LOSS_WRITE_OFF: {payload.notes.strip()}"

        balance.in_use_qty -= payload.write_off_qty

        if do_line is not None:
            if do_line.returned_qty + do_line.lost_qty + payload.write_off_qty > do_line.dispatched_qty:
                raise ReconciliationBoundsError(
                    "Loss write-off exceeds Delivery Order line dispatched quantity."
                )
            do_line.lost_qty += payload.write_off_qty

        rec.lost_qty += payload.write_off_qty

        parent_do = self.repository.lock_delivery_order(ctx.organization_id, rec.delivery_order_id)
        ref_num = parent_do.do_number if parent_do else str(rec.delivery_order_id)

        db.add(
            StockMovement(
                organization_id=ctx.organization_id,
                item_id=rec.item_id,
                equipment_unit_id=rec.equipment_unit_id,
                project_id=rec.project_id,
                ownership_source=payload.ownership_source.value,
                movement_type=MovementType.LOSS_WRITE_OFF.value,
                from_bucket=StockBucket.IN_USE.value,
                to_bucket=StockBucket.LOST.value,
                quantity=payload.write_off_qty,
                reference_type=ReferenceType.RECONCILIATION.value,
                reference_number=ref_num,
                notes=payload.notes.strip(),
                created_by=ctx.user_id,
            )
        )

        db.flush()
        db.refresh(rec)

        if rec.variance_qty == Decimal("0"):
            if (
                payload.resolve_if_zero
                or rec.reconciliation_status == ReconciliationStatus.DISCREPANCY.value
            ):
                rec.reconciliation_status = ReconciliationStatus.RESOLVED.value
                rec.resolved_by = ctx.user_id
                rec.resolved_at = datetime.now(UTC)
            else:
                rec.reconciliation_status = ReconciliationStatus.EQUALIZED.value

        if parent_do is not None and parent_do.lines:
            all_closed = all(
                (dl.returned_qty + dl.lost_qty) == dl.dispatched_qty for dl in parent_do.lines
            )
            if all_closed:
                parent_do.status = DeliveryOrderStatus.CLOSED.value

        db.commit()
        joined = self.repository.get_record_joined(ctx.organization_id, recon_id)
        assert joined is not None
        return _to_recon_response(*joined)

    def resolve_discrepancy(
        self,
        ctx: CurrentUserContext,
        recon_id: UUID,
        payload: ResolveDiscrepancyRequest,
    ) -> ReconciliationRecordResponse:
        rec = self.repository.get_for_update(ctx.organization_id, recon_id)
        if rec is None:
            raise NotFoundError(
                "Reconciliation record not found.",
                details={"reconciliation_id": str(recon_id)},
            )
        if rec.reconciliation_status == ReconciliationStatus.RESOLVED.value:
            raise InvalidStateTransitionError("Reconciliation record is already RESOLVED.")
        rec.reconciliation_status = ReconciliationStatus.RESOLVED.value
        rec.resolved_by = ctx.user_id
        rec.resolved_at = datetime.now(UTC)
        self.repository.db.commit()
        joined = self.repository.get_record_joined(ctx.organization_id, recon_id)
        assert joined is not None
        return _to_recon_response(*joined)
