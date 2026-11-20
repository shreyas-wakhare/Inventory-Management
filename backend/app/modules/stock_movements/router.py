"""FastAPI router definitions and dependency wiring for the stock_movements domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.stock_movements.controller import StockMovementController
from app.modules.stock_movements.repository import StockMovementRepository
from app.modules.stock_movements.schemas import StockMovementModuleStatus
from app.modules.stock_movements.service import StockMovementService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/stock-movements", tags=["stock-movements"])


def get_controller(db: DbSession) -> StockMovementController:
    """Wire repository -> service -> controller for request scope."""
    repository = StockMovementRepository(db)
    service = StockMovementService(repository)
    return StockMovementController(service)


@router.get("/status", response_model=APIResponse[StockMovementModuleStatus])
def module_status(
    controller: StockMovementController = Depends(get_controller),
) -> APIResponse[StockMovementModuleStatus]:
    """Scaffold endpoint verifying stock_movements router -> controller -> service -> repository wiring."""
    return controller.get_status()