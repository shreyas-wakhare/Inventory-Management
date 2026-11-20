"""Business logic and transaction service layer for the stock_movements domain."""

from app.modules.stock_movements.repository import StockMovementRepository
from app.modules.stock_movements.schemas import StockMovementModuleStatus


class StockMovementService:
    """Orchestrates business rules and atomic transactions for stock_movements."""

    def __init__(self, repository: StockMovementRepository) -> None:
        self.repository = repository

    def get_status(self) -> StockMovementModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return StockMovementModuleStatus(**payload)