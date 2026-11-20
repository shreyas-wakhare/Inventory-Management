"""FastAPI router definitions and dependency wiring for the projects domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.projects.controller import ProjectController
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import ProjectModuleStatus
from app.modules.projects.service import ProjectService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def get_controller(db: DbSession) -> ProjectController:
    """Wire repository -> service -> controller for request scope."""
    repository = ProjectRepository(db)
    service = ProjectService(repository)
    return ProjectController(service)


@router.get("/status", response_model=APIResponse[ProjectModuleStatus])
def module_status(
    controller: ProjectController = Depends(get_controller),
) -> APIResponse[ProjectModuleStatus]:
    """Scaffold endpoint verifying projects router -> controller -> service -> repository wiring."""
    return controller.get_status()