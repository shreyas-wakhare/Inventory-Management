"""Business logic and transaction service layer for the items domain."""

from app.modules.items.repository import ItemRepository
from app.modules.items.schemas import ItemModuleStatus


class ItemService:
    """Orchestrates business rules and atomic transactions for items."""

    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    def get_status(self) -> ItemModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return ItemModuleStatus(**payload)