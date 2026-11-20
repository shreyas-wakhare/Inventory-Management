"""FastAPI router definitions and dependency wiring for the collection_orders domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.collection_orders.controller import CollectionOrderController
from app.modules.collection_orders.repository import CollectionOrderRepository
from app.modules.collection_orders.schemas import CollectionOrderModuleStatus
from app.modules.collection_orders.service import CollectionOrderService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/collection-orders", tags=["collection-orders"])


def get_controller(db: DbSession) -> CollectionOrderController:
    """Wire repository -> service -> controller for request scope."""
    repository = CollectionOrderRepository(db)
    service = CollectionOrderService(repository)
    return CollectionOrderController(service)


@router.get("/status", response_model=APIResponse[CollectionOrderModuleStatus])
def module_status(
    controller: CollectionOrderController = Depends(get_controller),
) -> APIResponse[CollectionOrderModuleStatus]:
    """Scaffold endpoint verifying collection_orders router -> controller -> service -> repository wiring."""
    return controller.get_status()