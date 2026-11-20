"""Business logic and transaction service layer for the delivery_orders domain."""

from app.modules.delivery_orders.repository import DeliveryOrderRepository
from app.modules.delivery_orders.schemas import DeliveryOrderModuleStatus


class DeliveryOrderService:
    """Orchestrates business rules and atomic transactions for delivery_orders."""

    def __init__(self, repository: DeliveryOrderRepository) -> None:
        self.repository = repository

    def get_status(self) -> DeliveryOrderModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return DeliveryOrderModuleStatus(**payload)