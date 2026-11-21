"""Business logic service for the items catalog."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import DuplicateBusinessKeyError, NotFoundError
from app.modules.items.models import Item
from app.modules.items.repository import ItemRepository
from app.modules.items.schemas import (
    CategoryFacetResponse,
    ItemBalanceSlice,
    ItemCreate,
    ItemDetailResponse,
    ItemResponse,
    ItemUpdate,
    ItemWithStockResponse,
)
from app.modules.stock_balances.models import StockBalance
from app.shared.enums import OwnershipSource, ProductType
from app.shared.schemas import PaginatedResponse, build_pagination_meta


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ItemService:
    """Manages master catalog items and stock-enriched catalog queries."""

    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    def list_items(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        product_type: ProductType | None = None,
        category: str | None = None,
        sub_category: str | None = None,
        is_active: bool | None = None,
        sort_by: str = "item_code",
    ) -> PaginatedResponse[ItemWithStockResponse]:
        rows, total = self.repository.list_items_with_stock(
            ctx.organization_id,
            search=search,
            product_type=product_type,
            category=category,
            sub_category=sub_category,
            is_active=is_active,
            sort_by=sort_by,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items: list[ItemWithStockResponse] = []
        for item, avail, in_use, repl, dmg in rows:
            total_qty = avail + in_use + repl + dmg
            items.append(
                ItemWithStockResponse(
                    **ItemResponse.model_validate(item).model_dump(),
                    available_qty=avail,
                    in_use_qty=in_use,
                    replenishment_qty=repl,
                    damaged_qty=dmg,
                    total_qty=total_qty,
                    total_value_aed=_money(total_qty * item.unit_price_aed),
                )
            )
        return PaginatedResponse(
            items=items,
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def get_categories(
        self,
        ctx: CurrentUserContext,
        *,
        product_type: ProductType | None = None,
    ) -> list[CategoryFacetResponse]:
        facets = self.repository.get_category_facets(
            ctx.organization_id,
            product_type=product_type,
        )
        return [
            CategoryFacetResponse(category=cat, sub_categories=subs, item_count=cnt)
            for cat, subs, cnt in facets
        ]

    def create_item(self, ctx: CurrentUserContext, payload: ItemCreate) -> ItemResponse:
        code = payload.item_code.strip().upper()
        if self.repository.get_by_code(ctx.organization_id, code) is not None:
            raise DuplicateBusinessKeyError(
                f"Item code '{code}' already exists in this organization.",
                details={"item_code": code},
            )

        is_serialized = payload.product_type == ProductType.ASSET
        item = Item(
            organization_id=ctx.organization_id,
            item_code=code,
            description=payload.description.strip(),
            uom=payload.uom.strip().upper(),
            product_type=payload.product_type.value,
            category=payload.category.strip(),
            sub_category=payload.sub_category.strip() if payload.sub_category else None,
            unit_price_aed=_money(payload.unit_price_aed),
            is_serialized=is_serialized,
            is_active=True,
        )
        self.repository.db.add(item)
        self.repository.db.flush()

        # Initialize default SER ownership balance row at 0 for immediate visibility
        self.repository.db.add(
            StockBalance(
                organization_id=ctx.organization_id,
                item_id=item.id,
                ownership_source=OwnershipSource.SER.value,
                available_qty=Decimal("0"),
                in_use_qty=Decimal("0"),
                replenishment_qty=Decimal("0"),
                damaged_qty=Decimal("0"),
            )
        )
        self.repository.db.commit()
        self.repository.db.refresh(item)
        return ItemResponse.model_validate(item)

    def get_item_detail(self, ctx: CurrentUserContext, item_id: UUID) -> ItemDetailResponse:
        item = self.repository.get_by_id(ctx.organization_id, item_id)
        if item is None:
            raise NotFoundError("Item not found.", details={"item_id": str(item_id)})

        balances = self.repository.get_balances_for_item(ctx.organization_id, item.id)
        slices: list[ItemBalanceSlice] = []
        avail = in_use = repl = dmg = Decimal("0")
        for bal in balances:
            t_qty = bal.available_qty + bal.in_use_qty + bal.replenishment_qty + bal.damaged_qty
            avail += bal.available_qty
            in_use += bal.in_use_qty
            repl += bal.replenishment_qty
            dmg += bal.damaged_qty
            slices.append(
                ItemBalanceSlice(
                    ownership_source=OwnershipSource(bal.ownership_source),
                    available_qty=bal.available_qty,
                    in_use_qty=bal.in_use_qty,
                    replenishment_qty=bal.replenishment_qty,
                    damaged_qty=bal.damaged_qty,
                    total_qty=t_qty,
                )
            )
        total_qty = avail + in_use + repl + dmg
        unit_counts = (
            self.repository.get_unit_status_counts(ctx.organization_id, item.id)
            if item.is_serialized
            else {}
        )
        return ItemDetailResponse(
            **ItemResponse.model_validate(item).model_dump(),
            available_qty=avail,
            in_use_qty=in_use,
            replenishment_qty=repl,
            damaged_qty=dmg,
            total_qty=total_qty,
            total_value_aed=_money(total_qty * item.unit_price_aed),
            balances_by_source=slices,
            unit_status_counts=unit_counts,
        )

    def update_item(
        self,
        ctx: CurrentUserContext,
        item_id: UUID,
        payload: ItemUpdate,
    ) -> ItemResponse:
        item = self.repository.get_by_id(ctx.organization_id, item_id)
        if item is None:
            raise NotFoundError("Item not found.", details={"item_id": str(item_id)})

        if payload.description is not None:
            item.description = payload.description.strip()
        if payload.uom is not None:
            item.uom = payload.uom.strip().upper()
        if payload.category is not None:
            item.category = payload.category.strip()
        if payload.sub_category is not None:
            item.sub_category = payload.sub_category.strip() or None
        if payload.unit_price_aed is not None:
            item.unit_price_aed = _money(payload.unit_price_aed)
        if payload.is_active is not None:
            item.is_active = payload.is_active

        self.repository.db.commit()
        self.repository.db.refresh(item)
        return ItemResponse.model_validate(item)
