"""HTTP controller layer for items catalog endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.items.schemas import (
    CategoryFacetResponse,
    ItemCreate,
    ItemDetailResponse,
    ItemResponse,
    ItemUpdate,
    ItemWithStockResponse,
)
from app.modules.items.service import ItemService
from app.shared.enums import ProductType
from app.shared.schemas import APIResponse, PaginatedResponse


class ItemController:
    """Coordinates HTTP envelopes for catalog items."""

    def __init__(self, service: ItemService) -> None:
        self.service = service

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
        return self.service.list_items(
            ctx,
            pagination,
            search=search,
            product_type=product_type,
            category=category,
            sub_category=sub_category,
            is_active=is_active,
            sort_by=sort_by,
        )

    def get_categories(
        self,
        ctx: CurrentUserContext,
        *,
        product_type: ProductType | None = None,
    ) -> APIResponse[list[CategoryFacetResponse]]:
        return APIResponse(data=self.service.get_categories(ctx, product_type=product_type))

    def create_item(
        self,
        ctx: CurrentUserContext,
        payload: ItemCreate,
    ) -> APIResponse[ItemResponse]:
        return APIResponse(data=self.service.create_item(ctx, payload), message="created")

    def get_item_detail(
        self,
        ctx: CurrentUserContext,
        item_id: UUID,
    ) -> APIResponse[ItemDetailResponse]:
        return APIResponse(data=self.service.get_item_detail(ctx, item_id))

    def update_item(
        self,
        ctx: CurrentUserContext,
        item_id: UUID,
        payload: ItemUpdate,
    ) -> APIResponse[ItemResponse]:
        return APIResponse(data=self.service.update_item(ctx, item_id, payload))
