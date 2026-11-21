"""FastAPI router definitions for /delivery-orders endpoints."""

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
from app.modules.delivery_orders.controller import DeliveryOrderController
from app.modules.delivery_orders.repository import DeliveryOrderRepository
from app.modules.delivery_orders.schemas import (
    CancelOrderRequest,
    DeliveryOrderCreate,
    DeliveryOrderDetailResponse,
    DeliveryOrderDispatchRequest,
    DeliveryOrderResponse,
    DeliveryOrderSummaryResponse,
    DeliveryOrderUpdate,
)
from app.modules.delivery_orders.service import DeliveryOrderService
from app.shared.enums import DeliveryOrderStatus, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/delivery-orders", tags=["delivery-orders"])


def get_controller(db: DbSession) -> DeliveryOrderController:
    return DeliveryOrderController(DeliveryOrderService(DeliveryOrderRepository(db)))


@router.get("", response_model=PaginatedResponse[DeliveryOrderSummaryResponse])
def list_delivery_orders(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    project_id: UUID | None = Query(default=None),
    order_status: DeliveryOrderStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    controller: DeliveryOrderController = Depends(get_controller),
) -> PaginatedResponse[DeliveryOrderSummaryResponse]:
    return controller.list_orders(
        current_user,
        pagination,
        project_id=project_id,
        status=order_status,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


@router.post(
    "",
    response_model=APIResponse[DeliveryOrderDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_delivery_order(
    payload: DeliveryOrderCreate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderDetailResponse]:
    return controller.create_order(current_user, payload)


@router.get("/{do_id}", response_model=APIResponse[DeliveryOrderDetailResponse])
def get_delivery_order(
    do_id: UUID,
    current_user: CurrentUserDep,
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderDetailResponse]:
    return controller.get_order_detail(current_user, do_id)


@router.patch("/{do_id}", response_model=APIResponse[DeliveryOrderDetailResponse])
def update_delivery_order(
    do_id: UUID,
    payload: DeliveryOrderUpdate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderDetailResponse]:
    return controller.update_order(current_user, do_id, payload)


@router.post("/{do_id}/dispatch", response_model=APIResponse[DeliveryOrderDetailResponse])
def dispatch_delivery_order(
    do_id: UUID,
    payload: DeliveryOrderDispatchRequest | None = None,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderDetailResponse]:
    return controller.dispatch_order(
        current_user,
        do_id,
        payload or DeliveryOrderDispatchRequest(),
    )


@router.post("/{do_id}/cancel", response_model=APIResponse[DeliveryOrderResponse])
def cancel_delivery_order(
    do_id: UUID,
    payload: CancelOrderRequest,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderResponse]:
    return controller.cancel_order(current_user, do_id, payload)
