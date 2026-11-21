"""HTTP controller layer for Delivery Orders endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
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
from app.shared.enums import DeliveryOrderStatus
from app.shared.schemas import APIResponse, PaginatedResponse


class DeliveryOrderController:
    """Coordinates HTTP envelopes for delivery order routes."""

    def __init__(self, service: DeliveryOrderService) -> None:
        self.service = service

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
        return self.service.list_orders(
            ctx,
            pagination,
            project_id=project_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )

    def create_order(
        self,
        ctx: CurrentUserContext,
        payload: DeliveryOrderCreate,
    ) -> APIResponse[DeliveryOrderDetailResponse]:
        return APIResponse(data=self.service.create_order(ctx, payload), message="created")

    def get_order_detail(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
    ) -> APIResponse[DeliveryOrderDetailResponse]:
        return APIResponse(data=self.service.get_order_detail(ctx, do_id))

    def update_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: DeliveryOrderUpdate,
    ) -> APIResponse[DeliveryOrderDetailResponse]:
        return APIResponse(data=self.service.update_order(ctx, do_id, payload))

    def dispatch_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: DeliveryOrderDispatchRequest,
    ) -> APIResponse[DeliveryOrderDetailResponse]:
        return APIResponse(
            data=self.service.dispatch_order(ctx, do_id, payload),
            message="dispatched",
        )

    def cancel_order(
        self,
        ctx: CurrentUserContext,
        do_id: UUID,
        payload: CancelOrderRequest,
    ) -> APIResponse[DeliveryOrderResponse]:
        return APIResponse(
            data=self.service.cancel_order(ctx, do_id, payload),
            message="cancelled",
        )
