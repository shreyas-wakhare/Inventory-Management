"""FastAPI router definitions and dependency wiring for the delivery_orders domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.delivery_orders.controller import DeliveryOrderController
from app.modules.delivery_orders.repository import DeliveryOrderRepository
from app.modules.delivery_orders.schemas import DeliveryOrderModuleStatus
from app.modules.delivery_orders.service import DeliveryOrderService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/delivery-orders", tags=["delivery-orders"])


def get_controller(db: DbSession) -> DeliveryOrderController:
    """Wire repository -> service -> controller for request scope."""
    repository = DeliveryOrderRepository(db)
    service = DeliveryOrderService(repository)
    return DeliveryOrderController(service)


@router.get("/status", response_model=APIResponse[DeliveryOrderModuleStatus])
def module_status(
    controller: DeliveryOrderController = Depends(get_controller),
) -> APIResponse[DeliveryOrderModuleStatus]:
    """Scaffold endpoint verifying delivery_orders router -> controller -> service -> repository wiring."""
    return controller.get_status()