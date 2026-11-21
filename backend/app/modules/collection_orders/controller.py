"""HTTP controller layer for Collection Orders endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
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
from app.shared.enums import CollectionOrderStatus
from app.shared.schemas import APIResponse, PaginatedResponse


class CollectionOrderController:
    """Coordinates HTTP envelopes for collection order routes."""

    def __init__(self, service: CollectionOrderService) -> None:
        self.service = service

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
        return self.service.list_orders(
            ctx,
            pagination,
            project_id=project_id,
            delivery_order_id=delivery_order_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )

    def create_order(
        self,
        ctx: CurrentUserContext,
        payload: CollectionOrderCreate,
    ) -> APIResponse[CollectionOrderDetailResponse]:
        return APIResponse(data=self.service.create_order(ctx, payload), message="created")

    def get_order_detail(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
    ) -> APIResponse[CollectionOrderDetailResponse]:
        return APIResponse(data=self.service.get_order_detail(ctx, co_id))

    def update_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionOrderUpdate,
    ) -> APIResponse[CollectionOrderDetailResponse]:
        return APIResponse(data=self.service.update_order(ctx, co_id, payload))

    def receive_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionOrderReceiveRequest,
    ) -> APIResponse[CollectionOrderDetailResponse]:
        return APIResponse(
            data=self.service.receive_order(ctx, co_id, payload),
            message="received",
        )

    def cancel_order(
        self,
        ctx: CurrentUserContext,
        co_id: UUID,
        payload: CollectionCancelRequest,
    ) -> APIResponse[CollectionOrderResponse]:
        return APIResponse(
            data=self.service.cancel_order(ctx, co_id, payload),
            message="cancelled",
        )
