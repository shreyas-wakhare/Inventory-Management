"""FastAPI router definitions for /collection-orders endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUserContext,
    CurrentUserDep,
    DbSession,
    PaginationDep,
    require_roles,
)
from app.modules.collection_orders.controller import CollectionOrderController
from app.modules.collection_orders.repository import CollectionOrderRepository
from app.modules.collection_orders.schemas import (
    CollectionCancelRequest,
    CollectionOrderCreate,
    CollectionOrderDetailResponse,
    CollectionOrderReceiveRequest,
    CollectionOrderResponse,
    CollectionOrderSummaryResponse,
    CollectionOrderUpdate,
)
from app.modules.collection_orders.service import CollectionOrderService
from app.shared.enums import CollectionOrderStatus, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/collection-orders", tags=["collection-orders"])


def get_controller(db: DbSession) -> CollectionOrderController:
    return CollectionOrderController(CollectionOrderService(CollectionOrderRepository(db)))


@router.get("", response_model=PaginatedResponse[CollectionOrderSummaryResponse])
def list_collection_orders(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    project_id: UUID | None = Query(default=None),
    delivery_order_id: UUID | None = Query(default=None),
    order_status: CollectionOrderStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    controller: CollectionOrderController = Depends(get_controller),
) -> PaginatedResponse[CollectionOrderSummaryResponse]:
    return controller.list_orders(
        current_user,
        pagination,
        project_id=project_id,
        delivery_order_id=delivery_order_id,
        status=order_status,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


@router.post(
    "",
    response_model=APIResponse[CollectionOrderDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_collection_order(
    payload: CollectionOrderCreate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR, UserRole.WORKSHOP_LEAD)
    ),
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderDetailResponse]:
    return controller.create_order(current_user, payload)


@router.get("/{co_id}", response_model=APIResponse[CollectionOrderDetailResponse])
def get_collection_order(
    co_id: UUID,
    current_user: CurrentUserDep,
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderDetailResponse]:
    return controller.get_order_detail(current_user, co_id)


@router.patch("/{co_id}", response_model=APIResponse[CollectionOrderDetailResponse])
def update_collection_order(
    co_id: UUID,
    payload: CollectionOrderUpdate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR, UserRole.WORKSHOP_LEAD)
    ),
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderDetailResponse]:
    return controller.update_order(current_user, co_id, payload)


@router.post("/{co_id}/receive", response_model=APIResponse[CollectionOrderDetailResponse])
def receive_collection_order(
    co_id: UUID,
    payload: CollectionOrderReceiveRequest | None = None,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR, UserRole.WORKSHOP_LEAD)
    ),
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderDetailResponse]:
    return controller.receive_order(
        current_user,
        co_id,
        payload or CollectionOrderReceiveRequest(),
    )


@router.post("/{co_id}/cancel", response_model=APIResponse[CollectionOrderResponse])
def cancel_collection_order(
    co_id: UUID,
    payload: CollectionCancelRequest,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR, UserRole.WORKSHOP_LEAD)
    ),
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderResponse]:
    return controller.cancel_order(current_user, co_id, payload)
