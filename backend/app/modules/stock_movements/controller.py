"""HTTP controller layer for the stock_movements domain."""

from app.modules.stock_movements.schemas import StockMovementModuleStatus
from app.modules.stock_movements.service import StockMovementService
from app.shared.schemas import APIResponse


class StockMovementController:
    """Coordinates HTTP request/response mapping for stock_movements routes."""

    def __init__(self, service: StockMovementService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[StockMovementModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)