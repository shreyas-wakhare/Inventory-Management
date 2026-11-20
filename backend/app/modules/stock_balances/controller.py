"""HTTP controller layer for the stock_balances domain."""

from app.modules.stock_balances.schemas import StockBalanceModuleStatus
from app.modules.stock_balances.service import StockBalanceService
from app.shared.schemas import APIResponse


class StockBalanceController:
    """Coordinates HTTP request/response mapping for stock_balances routes."""

    def __init__(self, service: StockBalanceService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[StockBalanceModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)