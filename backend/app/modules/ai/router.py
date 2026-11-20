"""FastAPI router definitions and dependency wiring for the ai domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.ai.controller import AIController
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import AIModuleStatus
from app.modules.ai.service import AIService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/ai", tags=["ai"])


def get_controller(db: DbSession) -> AIController:
    """Wire repository -> service -> controller for request scope."""
    repository = AIRepository(db)
    service = AIService(repository)
    return AIController(service)


@router.get("/status", response_model=APIResponse[AIModuleStatus])
def module_status(
    controller: AIController = Depends(get_controller),
) -> APIResponse[AIModuleStatus]:
    """Scaffold endpoint verifying ai router -> controller -> service -> repository wiring."""
    return controller.get_status()