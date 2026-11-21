"""Business & transaction service layer for Delivery Orders (SDD-2 Section 5.1)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    DuplicateBusinessKeyError,
    InsufficientStockError,
    InvalidStateTransitionError,
    NotFoundError,
    ProjectNotActiveError,
    UnitLockedInReplenishmentError,
    UnitNotAvailableError,
    ValidationDomainError,
)
from app.modules.delivery_orders.models import DeliveryOrder, DeliveryOrderLine
from app.modules.delivery_orders.repository import DeliveryOrderRepository
from app.modules.delivery_orders.schemas import (
    CancelOrderRequest,
    DeliveryOrderCreate,
    DeliveryOrderDetailResponse,
    DeliveryOrderDispatchRequest,
    DeliveryOrderLineCreate,
    DeliveryOrderLineResponse,
    DeliveryOrderResponse,
    DeliveryOrderSummaryResponse,
    DeliveryOrderUpdate,
)
from app.modules.reconciliation.models import ReconciliationRecord
from app.modules.stock_movements.models import StockMovement
from app.shared.enums import (
    DeliveryOrderStatus,
    EquipmentUnitStatus,
    MovementType,
    OwnershipSource,
    ProjectStatus,
    ReconciliationStatus,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta


class DeliveryOrderService:
    """Orchestrates DO drafts, atomic dispatch with Pre-Dispatch Replenishment Lock, and cancellation."""

    def __init__(self, repository: DeliveryOrderRepository) -> None:
        self.repository = repository

    def _validate_draft_lines(
        self,
        organization_id: UUID,
        lines: list[DeliveryOrderLineCreate],
    ) -> None:
        if not lines:
            raise ValidationDomainError(
                "Delivery order must contain at least one line.",
                details={"error_reason": "EMPTY_ORDER_LINES"},
            )
        item_ids = list({line.item_id for line in lines})
        items_map = self.repository.get_items_by_ids(organization_id, item_ids)
        seen_units: set[UUID] = set()

        for idx, line in enumerate(lines):
            item = items_map.get(line.item_id)
            if item is None:
                raise NotFoundError(
                    "Referenced catalog item not found.",
                    details={"line_index": idx, "item_id": str(line.item_id)},
                )
            if item.is_serialized:
                if line.equipment_unit_id is None:
                    raise ValidationDomainError(
                        f"Serialized ASSET '{item.item_code}' requires equipment_unit_id.",
                        details={"line_index": idx, "item_code": item.item_code},
                    )
                if line.dispatched_qty != Decimal("1"):
                    raise ValidationDomainError(
                        f"Serialized ASSET '{item.item_code}' must have dispatched_qty = 1.",
                        details={"line_index": idx, "item_code": item.item_code},
                    )
                if line.equipment_unit_id in seen_units:
                    raise ValidationDomainError(
                        "Duplicate equipment_unit_id within the same Delivery Order.",
                        details={"equipment_unit_id": str(line.equipment_unit_id)},
                    )
                seen_units.add(line.equipment_unit_id)
            elif line.equipment_unit_id is not None:
                raise ValidationDomainError(
                    f"Bulk ACCESSORY '{item.item_code}' must not specify equipment_unit_id.",
                    details={"line_index": idx, "item_code": item.item_code},
                )

    def _build_detail_response(
        self,
        organization_id: UUID,
        do_id: UUID,
    ) -> DeliveryOrderDetailResponse:
        parts = self.repository.get_order_detail_parts(organization_id, do_id)
        if parts is None:
            raise NotFoundError("Delivery order not found.", details={"delivery_order_id": str(do_id)})
        do, project, user, line_rows = parts
        lines_out = [
            DeliveryOrderLineResponse(
                id=line.id,
                delivery_order_id=line.delivery_order_id,
                item_id=line.item_id,
                item_code=item.item_code,
                item_description=item.description,
                uom=item.uom,
                equipment_unit_id=line.equipment_unit_id,
                serial_number=unit.serial_number if unit else None,
                ownership_source=OwnershipSource(line.ownership_source),
                dispatched_qty=line.dispatched_qty,
                returned_qty=line.returned_qty,
                lost_qty=line.lost_qty,
                remaining_qty=line.dispatched_qty - line.returned_qty - line.lost_qty,
                created_at=line.created_at,
            )
            for line, item, unit in line_rows
        ]
        return DeliveryOrderDetailResponse(
            id=do.id,
            organization_id=do.organization_id,
            do_number=do.do_number,
            project_id=do.project_id,
            project_code=project.project_code,
            project_name=project.project_name,
            dispatch_date=do.dispatch_date,
            status=DeliveryOrderStatus(do.status),
            remarks=do.remarks,
            created_by=do.created_by,
            created_by_name=user.full_name,
            created_at=do.created_at,
            updated_at=do.updated_at,
            lines=lines_out,
        )

    def list_orders(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        project_id: UUID | None = None,
        status: DeliveryOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[DeliveryOrderSummaryResponse]:
        rows, total = self.repository.list_orders(
            ctx.organization_id,
            project_id=project_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search=search,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items = [
            DeliveryOrderSummaryResponse(
                id=do.id,
                organization_id=do.organization_id,
                do_number=do.do_number,
                project_id=do.project_id,
                project_code=prj.project_code,
                project_name=prj.project_name,
                dispatch_date=do.dispatch_date,
                status=DeliveryOrderStatus(do.status),
                remarks=do.remarks,
                created_by=do.created_by,
                created_by_name=usr.full_name,
                created_at=do.created_at,
                updated_at=do.updated_at,
                line_count=line_count,
                total_dispatched_qty=dispatched,
                total_returned_qty=returned,
                total_outstanding_qty=outstanding,
            )
            for do, prj, usr, line_count, dispatched, returned, outstanding in rows
        ]
        return PaginatedResponse(
            items=items,
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def get_order_detail(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
    ) -> DeliveryOrderDetailResponse:
        return self._build_detail_response(ctx.organization_id, do_id)

    def create_order(
        self,
        ctx: CurrentUserContext,
        payload: DeliveryOrderCreate,
    ) -> DeliveryOrderDetailResponse:
        do_number = payload.do_number.strip().upper()
        if self.repository.get_by_number(ctx.organization_id, do_number) is not None:
            raise DuplicateBusinessKeyError(
                f"Delivery order '{do_number}' already exists in this organization.",
                details={"do_number": do_number},
            )
        project = self.repository.get_project_for_org(ctx.organization_id, payload.project_id)
        if project is None:
            raise NotFoundError("Project not found.", details={"project_id": str(payload.project_id)})
        if project.status != ProjectStatus.ACTIVE.value:
            raise ProjectNotActiveError(
                f"Project '{project.project_code}' is '{project.status}' and cannot receive new DOs.",
                details={"project_code": project.project_code, "status": project.status},
            )

        self._validate_draft_lines(ctx.organization_id, payload.lines)

        do = DeliveryOrder(
            organization_id=ctx.organization_id,
            do_number=do_number,
            project_id=project.id,
            dispatch_date=payload.dispatch_date or date.today(),
            status=DeliveryOrderStatus.DRAFT.value,
            remarks=payload.remarks.strip() if payload.remarks else None,
            created_by=ctx.user_id,
        )
        for line in payload.lines:
            do.lines.append(
                DeliveryOrderLine(
                    item_id=line.item_id,
                    equipment_unit_id=line.equipment_unit_id,
                    ownership_source=line.ownership_source.value,
                    dispatched_qty=line.dispatched_qty,
                    returned_qty=Decimal("0"),
                    lost_qty=Decimal("0"),
                )
            )
        self.repository.db.add(do)
        self.repository.db.commit()
        return self._build_detail_response(ctx.organization_id, do.id)

    def update_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: DeliveryOrderUpdate,
    ) -> DeliveryOrderDetailResponse:
        do = self.repository.get_by_id(ctx.organization_id, do_id, for_update=True, with_lines=True)
        if do is None:
            raise NotFoundError("Delivery order not found.", details={"delivery_order_id": str(do_id)})
        if do.status != DeliveryOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Only DRAFT delivery orders can be edited (current status: {do.status}).",
                details={"status": do.status},
            )

        if payload.dispatch_date is not None:
            do.dispatch_date = payload.dispatch_date
        if payload.remarks is not None:
            do.remarks = payload.remarks.strip() or None
        if payload.lines is not None:
            self._validate_draft_lines(ctx.organization_id, payload.lines)
            do.lines.clear()
            self.repository.db.flush()
            for line in payload.lines:
                do.lines.append(
                    DeliveryOrderLine(
                        item_id=line.item_id,
                        equipment_unit_id=line.equipment_unit_id,
                        ownership_source=line.ownership_source.value,
                        dispatched_qty=line.dispatched_qty,
                        returned_qty=Decimal("0"),
                        lost_qty=Decimal("0"),
                    )
                )

        self.repository.db.commit()
        return self._build_detail_response(ctx.organization_id, do.id)

    def dispatch_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: DeliveryOrderDispatchRequest,
    ) -> DeliveryOrderDetailResponse:
        db = self.repository.db
        do = self.repository.get_by_id(ctx.organization_id, do_id, for_update=True, with_lines=True)
        if do is None:
            raise NotFoundError("Delivery order not found.", details={"delivery_order_id": str(do_id)})
        if do.status != DeliveryOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Cannot dispatch delivery order in '{do.status}' status; expected 'DRAFT'.",
                details={"do_number": do.do_number, "current_status": do.status},
            )
        if not do.lines:
            raise ValidationDomainError(
                "Cannot dispatch a delivery order with zero lines.",
                details={"error_reason": "EMPTY_ORDER_LINES"},
            )

        project = self.repository.get_project_for_org(ctx.organization_id, do.project_id)
        if project is None or project.status != ProjectStatus.ACTIVE.value:
            raise ProjectNotActiveError(
                "Target project must be ACTIVE before dispatching a Delivery Order.",
                details={"project_id": str(do.project_id)},
            )

        item_ids = list({line.item_id for line in do.lines})
        unit_ids = [line.equipment_unit_id for line in do.lines if line.equipment_unit_id is not None]

        items_map = self.repository.get_items_by_ids(ctx.organization_id, item_ids)
        # Deterministic ORDER BY id ASC row locking to prevent deadlocks
        units_map = self.repository.lock_units_ordered(ctx.organization_id, unit_ids)
        balances_map = self.repository.lock_balances_ordered(ctx.organization_id, item_ids)

        requested_by_bucket: dict[tuple[UUID, str], Decimal] = defaultdict(Decimal)

        # Pass 1: Pre-Dispatch Replenishment Lock & Availability Gates
        for line in do.lines:
            item = items_map.get(line.item_id)
            if item is None:
                raise NotFoundError("Item not found.", details={"item_id": str(line.item_id)})

            if item.is_serialized:
                if line.equipment_unit_id is None or line.dispatched_qty != Decimal("1"):
                    raise ValidationDomainError(
                        f"Serialized ASSET '{item.item_code}' requires equipment_unit_id and qty = 1."
                    )
                unit = units_map.get(line.equipment_unit_id)
                if unit is None or unit.item_id != item.id:
                    raise NotFoundError(
                        "Equipment unit not found for this catalog item.",
                        details={"equipment_unit_id": str(line.equipment_unit_id)},
                    )
                if unit.status == EquipmentUnitStatus.REPLENISHMENT.value:
                    raise UnitLockedInReplenishmentError(
                        f"Equipment unit '{unit.serial_number}' is locked in workshop REPLENISHMENT and cannot be dispatched.",
                        details={
                            "equipment_unit_id": str(unit.id),
                            "serial_number": unit.serial_number,
                            "current_status": unit.status,
                        },
                    )
                if unit.status != EquipmentUnitStatus.AVAILABLE.value or unit.current_project_id is not None:
                    raise UnitNotAvailableError(
                        f"Equipment unit '{unit.serial_number}' is currently '{unit.status}' and not available for dispatch.",
                        details={
                            "equipment_unit_id": str(unit.id),
                            "serial_number": unit.serial_number,
                            "current_status": unit.status,
                        },
                    )

            requested_by_bucket[(line.item_id, line.ownership_source)] += line.dispatched_qty

        for (item_id, source), req_qty in requested_by_bucket.items():
            balance = balances_map.get((item_id, source))
            avail_qty = balance.available_qty if balance is not None else Decimal("0")
            if avail_qty < req_qty:
                item = items_map[item_id]
                raise InsufficientStockError(
                    f"Insufficient AVAILABLE stock for '{item.item_code}' ({source}): requested {req_qty}, available {avail_qty}.",
                    details={
                        "item_id": str(item_id),
                        "item_code": item.item_code,
                        "ownership_source": source,
                        "requested_qty": str(req_qty),
                        "available_qty": str(avail_qty),
                    },
                )

        # Pass 2: Atomic state mutation
        if payload.dispatch_date is not None:
            do.dispatch_date = payload.dispatch_date
        if payload.remarks is not None:
            do.remarks = payload.remarks.strip() or do.remarks

        for line in do.lines:
            if line.equipment_unit_id is not None:
                unit = units_map[line.equipment_unit_id]
                unit.status = EquipmentUnitStatus.IN_USE.value
                unit.current_project_id = do.project_id

            balance = balances_map[(line.item_id, line.ownership_source)]
            balance.available_qty -= line.dispatched_qty
            balance.in_use_qty += line.dispatched_qty

            db.add(
                StockMovement(
                    organization_id=ctx.organization_id,
                    item_id=line.item_id,
                    equipment_unit_id=line.equipment_unit_id,
                    project_id=do.project_id,
                    ownership_source=line.ownership_source,
                    movement_type=MovementType.DO_DISPATCH.value,
                    from_bucket=StockBucket.AVAILABLE.value,
                    to_bucket=StockBucket.IN_USE.value,
                    quantity=line.dispatched_qty,
                    reference_type=ReferenceType.DELIVERY_ORDER.value,
                    reference_number=do.do_number,
                    notes=do.remarks,
                    created_by=ctx.user_id,
                )
            )

            recon = self.repository.find_reconciliation_for_update(
                ctx.organization_id,
                do.id,
                line.item_id,
                line.equipment_unit_id,
            )
            if recon is None:
                db.add(
                    ReconciliationRecord(
                        organization_id=ctx.organization_id,
                        project_id=do.project_id,
                        delivery_order_id=do.id,
                        item_id=line.item_id,
                        equipment_unit_id=line.equipment_unit_id,
                        outgoing_qty=line.dispatched_qty,
                        incoming_qty=Decimal("0"),
                        lost_qty=Decimal("0"),
                        reconciliation_status=ReconciliationStatus.OPEN.value,
                    )
                )
            else:
                recon.outgoing_qty += line.dispatched_qty
                recon.reconciliation_status = ReconciliationStatus.OPEN.value

        do.status = DeliveryOrderStatus.DISPATCHED.value
        db.commit()
        return self._build_detail_response(ctx.organization_id, do.id)

    def cancel_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: CancelOrderRequest,
    ) -> DeliveryOrderResponse:
        do = self.repository.get_by_id(ctx.organization_id, do_id, for_update=True, with_lines=False)
        if do is None:
            raise NotFoundError("Delivery order not found.", details={"delivery_order_id": str(do_id)})
        if do.status != DeliveryOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Only DRAFT delivery orders can be cancelled (current status: {do.status}).",
                details={"current_status": do.status},
            )
        do.status = DeliveryOrderStatus.CANCELLED.value
        do.remarks = f"Cancelled: {payload.reason.strip()}"
        self.repository.db.commit()
        detail = self._build_detail_response(ctx.organization_id, do.id)
        return DeliveryOrderResponse(**detail.model_dump(exclude={"lines"}))
