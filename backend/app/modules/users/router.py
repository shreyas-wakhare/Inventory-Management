"""FastAPI router definitions and dependency wiring for the users domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.users.controller import UserController
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserModuleStatus
from app.modules.users.service import UserService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/users", tags=["users"])


def get_controller(db: DbSession) -> UserController:
    """Wire repository -> service -> controller for request scope."""
    repository = UserRepository(db)
    service = UserService(repository)
    return UserController(service)


@router.get("/status", response_model=APIResponse[UserModuleStatus])
def module_status(
    controller: UserController = Depends(get_controller),
) -> APIResponse[UserModuleStatus]:
    """Scaffold endpoint verifying users router -> controller -> service -> repository wiring."""
    return controller.get_status()