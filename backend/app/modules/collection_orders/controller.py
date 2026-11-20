"""HTTP controller layer for the collection_orders domain."""

from app.modules.collection_orders.schemas import CollectionOrderModuleStatus
from app.modules.collection_orders.service import CollectionOrderService
from app.shared.schemas import APIResponse


class CollectionOrderController:
    """Coordinates HTTP request/response mapping for collection_orders routes."""

    def __init__(self, service: CollectionOrderService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[CollectionOrderModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)