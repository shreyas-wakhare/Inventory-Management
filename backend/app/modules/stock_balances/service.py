"""Business logic and transaction service layer for the stock_balances domain."""

from app.modules.stock_balances.repository import StockBalanceRepository
from app.modules.stock_balances.schemas import StockBalanceModuleStatus


class StockBalanceService:
    """Orchestrates business rules and atomic transactions for stock_balances."""

    def __init__(self, repository: StockBalanceRepository) -> None:
        self.repository = repository

    def get_status(self) -> StockBalanceModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return StockBalanceModuleStatus(**payload)