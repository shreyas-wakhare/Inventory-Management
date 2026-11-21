"""FastAPI router definitions for /items endpoints."""

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
from app.modules.items.controller import ItemController
from app.modules.items.repository import ItemRepository
from app.modules.items.schemas import (
    CategoryFacetResponse,
    ItemCreate,
    ItemDetailResponse,
    ItemResponse,
    ItemUpdate,
    ItemWithStockResponse,
)
from app.modules.items.service import ItemService
from app.shared.enums import ProductType, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/items", tags=["items"])


def get_controller(db: DbSession) -> ItemController:
    return ItemController(ItemService(ItemRepository(db)))


@router.get("", response_model=PaginatedResponse[ItemWithStockResponse])
def list_items(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    search: str | None = Query(default=None),
    product_type: ProductType | None = Query(default=None),
    category: str | None = Query(default=None),
    sub_category: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    sort_by: str = Query(
        default="item_code",
        pattern="^(item_code|category|unit_price_aed|available_qty)$",
    ),
    controller: ItemController = Depends(get_controller),
) -> PaginatedResponse[ItemWithStockResponse]:
    return controller.list_items(
        current_user,
        pagination,
        search=search,
        product_type=product_type,
        category=category,
        sub_category=sub_category,
        is_active=is_active,
        sort_by=sort_by,
    )


@router.get("/categories", response_model=APIResponse[list[CategoryFacetResponse]])
def get_item_categories(
    current_user: CurrentUserDep,
    product_type: ProductType | None = Query(default=None),
    controller: ItemController = Depends(get_controller),
) -> APIResponse[list[CategoryFacetResponse]]:
    return controller.get_categories(current_user, product_type=product_type)


@router.post("", response_model=APIResponse[ItemResponse], status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: ItemController = Depends(get_controller),
) -> APIResponse[ItemResponse]:
    return controller.create_item(current_user, payload)


@router.get("/{item_id}", response_model=APIResponse[ItemDetailResponse])
def get_item(
    item_id: UUID,
    current_user: CurrentUserDep,
    controller: ItemController = Depends(get_controller),
) -> APIResponse[ItemDetailResponse]:
    return controller.get_item_detail(current_user, item_id)


@router.patch("/{item_id}", response_model=APIResponse[ItemResponse])
def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: ItemController = Depends(get_controller),
) -> APIResponse[ItemResponse]:
    return controller.update_item(current_user, item_id, payload)
