"""HTTP controller layer for the delivery_orders domain."""

from app.modules.delivery_orders.schemas import DeliveryOrderModuleStatus
from app.modules.delivery_orders.service import DeliveryOrderService
from app.shared.schemas import APIResponse


class DeliveryOrderController:
    """Coordinates HTTP request/response mapping for delivery_orders routes."""

    def __init__(self, service: DeliveryOrderService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[DeliveryOrderModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)