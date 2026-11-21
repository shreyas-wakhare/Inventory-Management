"""FastAPI router definitions for the isolated /ai boundary."""

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserDep, DbSession
from app.modules.ai.controller import AIController
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import AIModuleStatus
from app.modules.ai.service import AIService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/ai", tags=["ai"])


def get_controller(db: DbSession) -> AIController:
    return AIController(AIService(AIRepository(db)))


@router.get("/status", response_model=APIResponse[AIModuleStatus])
def module_status(
    _: CurrentUserDep,
    controller: AIController = Depends(get_controller),
) -> APIResponse[AIModuleStatus]:
    return controller.get_status()
