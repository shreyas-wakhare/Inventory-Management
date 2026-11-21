"""Business logic service for stock balances, opening stock, and manual adjustments."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    InsufficientStockError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationDomainError,
)
from app.modules.items.models import Item
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_balances.repository import StockBalanceRepository
from app.modules.stock_balances.schemas import (
    CategoryStockSummaryResponse,
    OpeningStockCreate,
    StockAdjustmentCreate,
    StockBalanceResponse,
)
from app.modules.stock_movements.models import StockMovement
from app.shared.enums import (
    ConditionStatus,
    MovementType,
    OwnershipSource,
    ProductType,
    ReferenceType,
    StockBucket,
)
from app.shared.schemas import PaginatedResponse, build_pagination_meta

BUCKET_TO_ATTR = {
    "AVAILABLE": "available_qty",
    "REPLENISHMENT": "replenishment_qty",
    "DAMAGED": "damaged_qty",
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_balance_response(balance: StockBalance, item: Item) -> StockBalanceResponse:
    total_qty = (
        balance.available_qty
        + balance.in_use_qty
        + balance.replenishment_qty
        + balance.damaged_qty
    )
    return StockBalanceResponse(
        id=balance.id,
        organization_id=balance.organization_id,
        item_id=balance.item_id,
        item_code=item.item_code,
        item_description=item.description,
        uom=item.uom,
        product_type=ProductType(item.product_type),
        category=item.category,
        sub_category=item.sub_category,
        unit_price_aed=item.unit_price_aed,
        ownership_source=OwnershipSource(balance.ownership_source),
        available_qty=balance.available_qty,
        in_use_qty=balance.in_use_qty,
        replenishment_qty=balance.replenishment_qty,
        damaged_qty=balance.damaged_qty,
        total_qty=total_qty,
        available_value_aed=_money(balance.available_qty * item.unit_price_aed),
        in_use_value_aed=_money(balance.in_use_qty * item.unit_price_aed),
        total_value_aed=_money(total_qty * item.unit_price_aed),
        updated_at=balance.updated_at,
    )


class StockBalanceService:
    """Manages live bucket queries, category summaries, opening stock, and manual adjustments."""

    def __init__(self, repository: StockBalanceRepository) -> None:
        self.repository = repository

    def list_balances(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        item_id: UUID | None = None,
        product_type: ProductType | None = None,
        category: str | None = None,
        ownership_source: OwnershipSource | None = None,
        has_replenishment: bool | None = None,
        has_damaged: bool | None = None,
        low_stock_only: bool | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[StockBalanceResponse]:
        rows, total = self.repository.list_balances(
            ctx.organization_id,
            item_id=item_id,
            product_type=product_type,
            category=category,
            ownership_source=ownership_source,
            has_replenishment=has_replenishment,
            has_damaged=has_damaged,
            low_stock_only=low_stock_only,
            search=search,
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

    def summarize_by_category(
        self,
        ctx: CurrentUserContext,
        *,
        product_type: ProductType | None = None,
        ownership_source: OwnershipSource | None = None,
    ) -> list[CategoryStockSummaryResponse]:
        rows = self.repository.summarize_by_category(
            ctx.organization_id,
            product_type=product_type,
            ownership_source=ownership_source,
        )
        return [
            CategoryStockSummaryResponse(
                category=str(r["category"]),
                item_count=int(r["item_count"]),  # type: ignore[arg-type]
                available_qty=r["available_qty"],  # type: ignore[arg-type]
                in_use_qty=r["in_use_qty"],  # type: ignore[arg-type]
                replenishment_qty=r["replenishment_qty"],  # type: ignore[arg-type]
                damaged_qty=r["damaged_qty"],  # type: ignore[arg-type]
                total_qty=r["total_qty"],  # type: ignore[arg-type]
                available_value_aed=_money(r["available_value_aed"]),  # type: ignore[arg-type]
                in_use_value_aed=_money(r["in_use_value_aed"]),  # type: ignore[arg-type]
                total_value_aed=_money(r["total_value_aed"]),  # type: ignore[arg-type]
            )
            for r in rows
        ]

    def record_opening_stock(
        self,
        ctx: CurrentUserContext,
        payload: OpeningStockCreate,
    ) -> StockBalanceResponse:
        item = self.repository.get_item_for_org(ctx.organization_id, payload.item_id)
        if item is None:
            raise NotFoundError("Item not found.", details={"item_id": str(payload.item_id)})
        if item.is_serialized:
            raise ValidationDomainError(
                "Opening stock for serialized ASSET items must be added via POST /api/v1/equipment-units.",
                details={"item_code": item.item_code},
            )

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
                available_qty=payload.quantity,
                in_use_qty=Decimal("0"),
                replenishment_qty=Decimal("0"),
                damaged_qty=Decimal("0"),
            )
            self.repository.db.add(balance)
        else:
            balance.available_qty += payload.quantity

        self.repository.db.add(
            StockMovement(
                organization_id=ctx.organization_id,
                item_id=item.id,
                equipment_unit_id=None,
                project_id=None,
                ownership_source=payload.ownership_source.value,
                movement_type=MovementType.OPENING_STOCK.value,
                from_bucket=StockBucket.EXTERNAL.value,
                to_bucket=StockBucket.AVAILABLE.value,
                quantity=payload.quantity,
                reference_type=ReferenceType.OPENING_BALANCE.value,
                reference_number=f"OPEN-{item.item_code}",
                notes=payload.notes.strip() if payload.notes else "Bulk opening stock entry",
                created_by=ctx.user_id,
            )
        )
        self.repository.db.commit()
        self.repository.db.refresh(balance)
        return _to_balance_response(balance, item)

    def record_adjustment(
        self,
        ctx: CurrentUserContext,
        payload: StockAdjustmentCreate,
    ) -> StockBalanceResponse:
        if payload.from_bucket == payload.to_bucket:
            raise ValidationDomainError("from_bucket and to_bucket must be different.")

        item = self.repository.get_item_for_org(ctx.organization_id, payload.item_id)
        if item is None:
            raise NotFoundError("Item not found.", details={"item_id": str(payload.item_id)})

        if item.is_serialized:
            if payload.equipment_unit_id is None:
                raise ValidationDomainError(
                    "equipment_unit_id is required when adjusting a serialized ASSET item."
                )
            if payload.quantity != Decimal("1"):
                raise ValidationDomainError("Serialized ASSET adjustment quantity must equal 1.")
        elif payload.equipment_unit_id is not None:
            raise ValidationDomainError(
                "equipment_unit_id must be omitted for bulk ACCESSORY items."
            )
        elif payload.to_bucket == "RETIRED":
            raise ValidationDomainError("RETIRED status is only valid for serialized ASSET units.")

        unit = None
        if payload.equipment_unit_id is not None:
            unit = self.repository.get_unit_for_update(
                ctx.organization_id,
                payload.equipment_unit_id,
            )
            if unit is None or unit.item_id != item.id:
                raise NotFoundError("Equipment unit not found for this item.")
            if unit.status != payload.from_bucket:
                raise InvalidStateTransitionError(
                    f"Equipment unit '{unit.serial_number}' is currently '{unit.status}', not '{payload.from_bucket}'.",
                    details={"serial_number": unit.serial_number, "current_status": unit.status},
                )

        balance = self.repository.get_balance_for_update(
            ctx.organization_id,
            item.id,
            payload.ownership_source.value,
        )
        if balance is None:
            raise InsufficientStockError(
                "No stock balance exists for the requested item and ownership source."
            )

        from_attr = BUCKET_TO_ATTR[payload.from_bucket]
        current_from_qty: Decimal = getattr(balance, from_attr)
        if current_from_qty < payload.quantity:
            raise InsufficientStockError(
                f"Insufficient quantity in {payload.from_bucket} bucket.",
                details={
                    "bucket": payload.from_bucket,
                    "available": str(current_from_qty),
                    "requested": str(payload.quantity),
                },
            )

        setattr(balance, from_attr, current_from_qty - payload.quantity)
        if payload.to_bucket != "RETIRED":
            to_attr = BUCKET_TO_ATTR[payload.to_bucket]
            setattr(balance, to_attr, getattr(balance, to_attr) + payload.quantity)

        if unit is not None:
            unit.status = payload.to_bucket
            if payload.to_bucket == "AVAILABLE":
                unit.condition_status = ConditionStatus.GOOD.value
            elif payload.to_bucket == "REPLENISHMENT":
                unit.condition_status = ConditionStatus.NEEDS_SERVICE.value
            elif payload.to_bucket == "DAMAGED":
                unit.condition_status = ConditionStatus.DAMAGED.value
            unit.notes = payload.notes.strip()

        self.repository.db.add(
            StockMovement(
                organization_id=ctx.organization_id,
                item_id=item.id,
                equipment_unit_id=unit.id if unit else None,
                project_id=None,
                ownership_source=payload.ownership_source.value,
                movement_type=MovementType.MANUAL_ADJUSTMENT.value,
                from_bucket=payload.from_bucket,
                to_bucket=payload.to_bucket,
                quantity=payload.quantity,
                reference_type=ReferenceType.ADJUSTMENT.value,
                reference_number=f"ADJ-{item.item_code}",
                notes=payload.notes.strip(),
                created_by=ctx.user_id,
            )
        )
        self.repository.db.commit()
        self.repository.db.refresh(balance)
        return _to_balance_response(balance, item)
