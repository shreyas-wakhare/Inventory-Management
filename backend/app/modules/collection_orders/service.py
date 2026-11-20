"""Business logic and transaction service layer for the collection_orders domain."""

from app.modules.collection_orders.repository import CollectionOrderRepository
from app.modules.collection_orders.schemas import CollectionOrderModuleStatus


class CollectionOrderService:
    """Orchestrates business rules and atomic transactions for collection_orders."""

    def __init__(self, repository: CollectionOrderRepository) -> None:
        self.repository = repository

    def get_status(self) -> CollectionOrderModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return CollectionOrderModuleStatus(**payload)