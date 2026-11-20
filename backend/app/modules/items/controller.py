"""HTTP controller layer for the items domain."""

from app.modules.items.schemas import ItemModuleStatus
from app.modules.items.service import ItemService
from app.shared.schemas import APIResponse


class ItemController:
    """Coordinates HTTP request/response mapping for items routes."""

    def __init__(self, service: ItemService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[ItemModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)