"""Business & transaction service layer for Collection Orders (SDD-2 Section 5.2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    DuplicateBusinessKeyError,
    InsufficientStockError,
    InvalidStateTransitionError,
    NotFoundError,
    ReconciliationBoundsError,
    UnitNotAtProjectError,
    ValidationDomainError,
)
from app.modules.collection_orders.models import CollectionOrder, CollectionOrderLine
from app.modules.collection_orders.repository import CollectionOrderRepository
from app.modules.collection_orders.schemas import (
    CollectionCancelRequest,
    CollectionOrderCreate,
    CollectionOrderDetailResponse,
    CollectionOrderLineCreate,
    CollectionOrderLineResponse,
    CollectionOrderReceiveRequest,
    CollectionOrderResponse,
    CollectionOrderSummaryResponse,
    CollectionOrderUpdate,
)
from app.modules.stock_movements.models import StockMovement
from app.shared.enums import (
    CollectionOrderStatus,
    ConditionStatus,
    DeliveryOrderStatus,
    EquipmentUnitStatus,
    MovementType,
    OwnershipSource,
    PostReturnBucket,
    ReconciliationStatus,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta

BUCKET_CONDITION_MAP = {
    PostReturnBucket.AVAILABLE.value: ConditionStatus.GOOD.value,
    PostReturnBucket.REPLENISHMENT.value: ConditionStatus.NEEDS_SERVICE.value,
    PostReturnBucket.DAMAGED.value: ConditionStatus.DAMAGED.value,
}

BUCKET_MOVEMENT_MAP = {
    PostReturnBucket.AVAILABLE.value: MovementType.CO_RETURN_AVAILABLE.value,
    PostReturnBucket.REPLENISHMENT.value: MovementType.CO_RETURN_REPLENISHMENT.value,
    PostReturnBucket.DAMAGED.value: MovementType.CO_RETURN_DAMAGED.value,
}

BUCKET_BALANCE_ATTR = {
    PostReturnBucket.AVAILABLE.value: "available_qty",
    PostReturnBucket.REPLENISHMENT.value: "replenishment_qty",
    PostReturnBucket.DAMAGED.value: "damaged_qty",
}


class CollectionOrderService:
    """Orchestrates CO drafts, atomic receipt routing, reconciliation sync, and DO closure."""

    def __init__(self, repository: CollectionOrderRepository) -> None:
        self.repository = repository

    def _validate_draft_lines(
        self,
        organization_id: UUID,
        lines: list[CollectionOrderLineCreate],
    ) -> None:
        if not lines:
            raise ValidationDomainError("Collection order must contain at least one line.")
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
                        f"Serialized ASSET '{item.item_code}' requires equipment_unit_id."
                    )
                if line.returned_qty != Decimal("1"):
                    raise ValidationDomainError(
                        f"Serialized ASSET '{item.item_code}' must have returned_qty = 1."
                    )
                if line.equipment_unit_id in seen_units:
                    raise ValidationDomainError(
                        "Duplicate equipment_unit_id within the same Collection Order."
                    )
                seen_units.add(line.equipment_unit_id)
            elif line.equipment_unit_id is not None:
                raise ValidationDomainError(
                    f"Bulk ACCESSORY '{item.item_code}' must not specify equipment_unit_id."
                )

    def _build_detail_response(
        self,
        organization_id: UUID,
        co_id: UUID,
    ) -> CollectionOrderDetailResponse:
        parts = self.repository.get_order_detail_parts(organization_id, co_id)
        if parts is None:
            raise NotFoundError(
                "Collection order not found.",
                details={"collection_order_id": str(co_id)},
            )
        co, project, do, user, line_rows = parts
        lines_out = [
            CollectionOrderLineResponse(
                id=line.id,
                collection_order_id=line.collection_order_id,
                delivery_order_line_id=line.delivery_order_line_id,
                item_id=line.item_id,
                item_code=item.item_code,
                item_description=item.description,
                uom=item.uom,
                equipment_unit_id=line.equipment_unit_id,
                serial_number=unit.serial_number if unit else None,
                ownership_source=OwnershipSource(line.ownership_source),
                returned_qty=line.returned_qty,
                post_return_bucket=PostReturnBucket(line.post_return_bucket),
                condition_notes=line.condition_notes,
                created_at=line.created_at,
            )
            for line, item, unit in line_rows
        ]
        return CollectionOrderDetailResponse(
            id=co.id,
            organization_id=co.organization_id,
            co_number=co.co_number,
            project_id=co.project_id,
            project_code=project.project_code,
            project_name=project.project_name,
            delivery_order_id=co.delivery_order_id,
            do_number=do.do_number if do else None,
            collection_date=co.collection_date,
            status=CollectionOrderStatus(co.status),
            remarks=co.remarks,
            created_by=co.created_by,
            created_by_name=user.full_name,
            created_at=co.created_at,
            updated_at=co.updated_at,
            lines=lines_out,
        )

    def list_orders(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        project_id: UUID | None = None,
        delivery_order_id: UUID | None = None,
        status: CollectionOrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[CollectionOrderSummaryResponse]:
        rows, total = self.repository.list_orders(
            ctx.organization_id,
            project_id=project_id,
            delivery_order_id=delivery_order_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search=search,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items = [
            CollectionOrderSummaryResponse(
                id=co.id,
                organization_id=co.organization_id,
                co_number=co.co_number,
                project_id=co.project_id,
                project_code=prj.project_code,
                project_name=prj.project_name,
                delivery_order_id=co.delivery_order_id,
                do_number=do.do_number if do else None,
                collection_date=co.collection_date,
                status=CollectionOrderStatus(co.status),
                remarks=co.remarks,
                created_by=co.created_by,
                created_by_name=usr.full_name,
                created_at=co.created_at,
                updated_at=co.updated_at,
                line_count=line_count,
                total_returned_qty=returned,
            )
            for co, prj, do, usr, line_count, returned in rows
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
        co_id: UUID,
    ) -> CollectionOrderDetailResponse:
        return self._build_detail_response(ctx.organization_id, co_id)

    def create_order(
        self,
        ctx: CurrentUserContext,
        payload: CollectionOrderCreate,
    ) -> CollectionOrderDetailResponse:
        co_number = payload.co_number.strip().upper()
        if self.repository.get_by_number(ctx.organization_id, co_number) is not None:
            raise DuplicateBusinessKeyError(
                f"Collection order '{co_number}' already exists in this organization.",
                details={"co_number": co_number},
            )
        project = self.repository.get_project_for_org(ctx.organization_id, payload.project_id)
        if project is None:
            raise NotFoundError("Project not found.", details={"project_id": str(payload.project_id)})

        if payload.delivery_order_id is not None:
            do = self.repository.get_delivery_order_for_org(
                ctx.organization_id,
                payload.delivery_order_id,
            )
            if do is None or do.project_id != project.id:
                raise NotFoundError(
                    "Referenced delivery order not found for this project.",
                    details={"delivery_order_id": str(payload.delivery_order_id)},
                )

        self._validate_draft_lines(ctx.organization_id, payload.lines)

        co = CollectionOrder(
            organization_id=ctx.organization_id,
            co_number=co_number,
            project_id=project.id,
            delivery_order_id=payload.delivery_order_id,
            collection_date=payload.collection_date or date.today(),
            status=CollectionOrderStatus.DRAFT.value,
            remarks=payload.remarks.strip() if payload.remarks else None,
            created_by=ctx.user_id,
        )
        for line in payload.lines:
            co.lines.append(
                CollectionOrderLine(
                    delivery_order_line_id=line.delivery_order_line_id,
                    item_id=line.item_id,
                    equipment_unit_id=line.equipment_unit_id,
                    ownership_source=line.ownership_source.value,
                    returned_qty=line.returned_qty,
                    post_return_bucket=line.post_return_bucket.value,
                    condition_notes=line.condition_notes.strip() if line.condition_notes else None,
                )
            )
        self.repository.db.add(co)
        self.repository.db.commit()
        return self._build_detail_response(ctx.organization_id, co.id)

    def update_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionOrderUpdate,
    ) -> CollectionOrderDetailResponse:
        co = self.repository.get_by_id(ctx.organization_id, co_id, for_update=True, with_lines=True)
        if co is None:
            raise NotFoundError(
                "Collection order not found.",
                details={"collection_order_id": str(co_id)},
            )
        if co.status != CollectionOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Only DRAFT collection orders can be edited (current status: {co.status}).",
                details={"current_status": co.status},
            )
        if payload.collection_date is not None:
            co.collection_date = payload.collection_date
        if payload.remarks is not None:
            co.remarks = payload.remarks.strip() or None
        if payload.lines is not None:
            self._validate_draft_lines(ctx.organization_id, payload.lines)
            co.lines.clear()
            self.repository.db.flush()
            for line in payload.lines:
                co.lines.append(
                    CollectionOrderLine(
                        delivery_order_line_id=line.delivery_order_line_id,
                        item_id=line.item_id,
                        equipment_unit_id=line.equipment_unit_id,
                        ownership_source=line.ownership_source.value,
                        returned_qty=line.returned_qty,
                        post_return_bucket=line.post_return_bucket.value,
                        condition_notes=(
                            line.condition_notes.strip() if line.condition_notes else None
                        ),
                    )
                )
        self.repository.db.commit()
        return self._build_detail_response(ctx.organization_id, co.id)

    def receive_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionOrderReceiveRequest,
    ) -> CollectionOrderDetailResponse:
        db = self.repository.db
        co = self.repository.get_by_id(ctx.organization_id, co_id, for_update=True, with_lines=True)
        if co is None:
            raise NotFoundError(
                "Collection order not found.",
                details={"collection_order_id": str(co_id)},
            )
        if co.status != CollectionOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Cannot receive collection order in '{co.status}' status; expected 'DRAFT'.",
                details={"co_number": co.co_number, "current_status": co.status},
            )
        if not co.lines:
            raise ValidationDomainError("Cannot receive a collection order with zero lines.")

        item_ids = list({line.item_id for line in co.lines})
        unit_ids = [line.equipment_unit_id for line in co.lines if line.equipment_unit_id is not None]
        explicit_do_line_ids = [
            line.delivery_order_line_id
            for line in co.lines
            if line.delivery_order_line_id is not None
        ]

        # Deterministic ORDER BY id ASC row locks
        units_map = self.repository.lock_units_ordered(ctx.organization_id, unit_ids)
        balances_map = self.repository.lock_balances_ordered(ctx.organization_id, item_ids)
        do_lines_map = self.repository.lock_do_lines_ordered(
            ctx.organization_id,
            explicit_do_line_ids,
        )

        touched_do_ids: set[UUID] = set()

        if payload.collection_date is not None:
            co.collection_date = payload.collection_date
        if payload.remarks is not None:
            co.remarks = payload.remarks.strip() or co.remarks

        for line in co.lines:
            # 1. Validate serialized unit custody
            if line.equipment_unit_id is not None:
                unit = units_map.get(line.equipment_unit_id)
                if unit is None or unit.item_id != line.item_id:
                    raise NotFoundError(
                        "Equipment unit not found for this item.",
                        details={"equipment_unit_id": str(line.equipment_unit_id)},
                    )
                if (
                    unit.status != EquipmentUnitStatus.IN_USE.value
                    or unit.current_project_id != co.project_id
                ):
                    raise UnitNotAtProjectError(
                        f"Equipment unit '{unit.serial_number}' is not currently IN_USE at this project.",
                        details={
                            "serial_number": unit.serial_number,
                            "current_status": unit.status,
                            "current_project_id": (
                                str(unit.current_project_id) if unit.current_project_id else None
                            ),
                        },
                    )

            # 2. Resolve originating DO line & enforce return bounds BEFORE aggregate balance check
            do_line_pair = None
            if line.delivery_order_line_id is not None:
                do_line_pair = do_lines_map.get(line.delivery_order_line_id)
                if do_line_pair is None:
                    raise NotFoundError(
                        "Referenced delivery_order_line_id not found.",
                        details={"delivery_order_line_id": str(line.delivery_order_line_id)},
                    )
                if do_line_pair[1].project_id != co.project_id:
                    raise ValidationDomainError(
                        "Referenced delivery_order_line belongs to a different project."
                    )
            else:
                do_line_pair = self.repository.find_matching_open_do_line_for_update(
                    ctx.organization_id,
                    project_id=co.project_id,
                    delivery_order_id=co.delivery_order_id,
                    item_id=line.item_id,
                    equipment_unit_id=line.equipment_unit_id,
                    ownership_source=line.ownership_source,
                )
                if do_line_pair is not None:
                    line.delivery_order_line_id = do_line_pair[0].id

            if do_line_pair is not None:
                do_line, parent_do = do_line_pair
                if (
                    do_line.returned_qty + do_line.lost_qty + line.returned_qty
                    > do_line.dispatched_qty
                ):
                    raise ReconciliationBoundsError(
                        "Returned quantity exceeds remaining dispatched quantity on the Delivery Order line.",
                        details={
                            "error_reason": "RETURN_EXCEEDS_DISPATCHED",
                            "delivery_order_line_id": str(do_line.id),
                            "dispatched_qty": str(do_line.dispatched_qty),
                            "already_returned_qty": str(do_line.returned_qty),
                            "already_lost_qty": str(do_line.lost_qty),
                            "attempted_return_qty": str(line.returned_qty),
                        },
                    )

            # 3. Validate aggregate in_use stock balance
            balance = balances_map.get((line.item_id, line.ownership_source))
            if balance is None or balance.in_use_qty < line.returned_qty:
                raise InsufficientStockError(
                    "Insufficient IN_USE stock balance for return.",
                    details={
                        "error_reason": "INSUFFICIENT_IN_USE_STOCK",
                        "item_id": str(line.item_id),
                        "ownership_source": line.ownership_source,
                        "in_use_qty": str(balance.in_use_qty if balance else Decimal("0")),
                        "returned_qty": str(line.returned_qty),
                    },
                )

            if do_line_pair is not None:
                do_line, parent_do = do_line_pair
                do_line.returned_qty += line.returned_qty
                touched_do_ids.add(parent_do.id)

                recon = self.repository.find_reconciliation_for_update(
                    ctx.organization_id,
                    parent_do.id,
                    line.item_id,
                    line.equipment_unit_id,
                )
                if recon is not None:
                    recon.incoming_qty += line.returned_qty
                    db.flush()
                    db.refresh(recon)
                    if (
                        recon.variance_qty == Decimal("0")
                        and recon.reconciliation_status != ReconciliationStatus.RESOLVED.value
                    ):
                        recon.reconciliation_status = ReconciliationStatus.EQUALIZED.value

            # 4. Route stock & equipment unit to post_return_bucket
            if line.equipment_unit_id is not None:
                unit = units_map[line.equipment_unit_id]
                unit.current_project_id = None
                unit.status = line.post_return_bucket
                unit.condition_status = BUCKET_CONDITION_MAP[line.post_return_bucket]
                if line.condition_notes:
                    unit.notes = line.condition_notes

            balance.in_use_qty -= line.returned_qty
            target_attr = BUCKET_BALANCE_ATTR[line.post_return_bucket]
            setattr(balance, target_attr, getattr(balance, target_attr) + line.returned_qty)

            db.add(
                StockMovement(
                    organization_id=ctx.organization_id,
                    item_id=line.item_id,
                    equipment_unit_id=line.equipment_unit_id,
                    project_id=co.project_id,
                    ownership_source=line.ownership_source,
                    movement_type=BUCKET_MOVEMENT_MAP[line.post_return_bucket],
                    from_bucket=StockBucket.IN_USE.value,
                    to_bucket=line.post_return_bucket,
                    quantity=line.returned_qty,
                    reference_type=ReferenceType.COLLECTION_ORDER.value,
                    reference_number=co.co_number,
                    notes=line.condition_notes or co.remarks,
                    created_by=ctx.user_id,
                )
            )

        # 5. Recompute parent Delivery Order status (PARTIALLY_RETURNED / CLOSED)
        db.flush()
        for parent_do_id in sorted(touched_do_ids):
            parent_do = self.repository.get_delivery_order_for_org(
                ctx.organization_id,
                parent_do_id,
                for_update=True,
            )
            if parent_do is not None and parent_do.lines:
                all_closed = all(
                    (dl.returned_qty + dl.lost_qty) == dl.dispatched_qty for dl in parent_do.lines
                )
                any_returned = any((dl.returned_qty + dl.lost_qty) > 0 for dl in parent_do.lines)
                if all_closed:
                    parent_do.status = DeliveryOrderStatus.CLOSED.value
                elif any_returned:
                    parent_do.status = DeliveryOrderStatus.PARTIALLY_RETURNED.value

        co.status = CollectionOrderStatus.RECEIVED.value
        db.commit()
        return self._build_detail_response(ctx.organization_id, co.id)

    def cancel_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionCancelRequest,
    ) -> CollectionOrderResponse:
        co = self.repository.get_by_id(ctx.organization_id, co_id, for_update=True, with_lines=False)
        if co is None:
            raise NotFoundError(
                "Collection order not found.",
                details={"collection_order_id": str(co_id)},
            )
        if co.status != CollectionOrderStatus.DRAFT.value:
            raise InvalidStateTransitionError(
                f"Only DRAFT collection orders can be cancelled (current status: {co.status}).",
                details={"current_status": co.status},
            )
        co.status = CollectionOrderStatus.CANCELLED.value
        co.remarks = f"Cancelled: {payload.reason.strip()}"
        self.repository.db.commit()
        detail = self._build_detail_response(ctx.organization_id, co.id)
        return CollectionOrderResponse(**detail.model_dump(exclude={"lines"}))
