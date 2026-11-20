"""FastAPI router definitions and dependency wiring for the stock_balances domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.stock_balances.controller import StockBalanceController
from app.modules.stock_balances.repository import StockBalanceRepository
from app.modules.stock_balances.schemas import StockBalanceModuleStatus
from app.modules.stock_balances.service import StockBalanceService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/stock-balances", tags=["stock-balances"])


def get_controller(db: DbSession) -> StockBalanceController:
    """Wire repository -> service -> controller for request scope."""
    repository = StockBalanceRepository(db)
    service = StockBalanceService(repository)
    return StockBalanceController(service)


@router.get("/status", response_model=APIResponse[StockBalanceModuleStatus])
def module_status(
    controller: StockBalanceController = Depends(get_controller),
) -> APIResponse[StockBalanceModuleStatus]:
    """Scaffold endpoint verifying stock_balances router -> controller -> service -> repository wiring."""
    return controller.get_status()