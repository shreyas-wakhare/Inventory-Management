"""FastAPI router definitions and dependency wiring for the items domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.items.controller import ItemController
from app.modules.items.repository import ItemRepository
from app.modules.items.schemas import ItemModuleStatus
from app.modules.items.service import ItemService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/items", tags=["items"])


def get_controller(db: DbSession) -> ItemController:
    """Wire repository -> service -> controller for request scope."""
    repository = ItemRepository(db)
    service = ItemService(repository)
    return ItemController(service)


@router.get("/status", response_model=APIResponse[ItemModuleStatus])
def module_status(
    controller: ItemController = Depends(get_controller),
) -> APIResponse[ItemModuleStatus]:
    """Scaffold endpoint verifying items router -> controller -> service -> repository wiring."""
    return controller.get_status()