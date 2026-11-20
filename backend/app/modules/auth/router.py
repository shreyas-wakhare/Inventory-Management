"""FastAPI router definitions and dependency wiring for the auth domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.auth.controller import AuthController
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AuthModuleStatus
from app.modules.auth.service import AuthService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def get_controller(db: DbSession) -> AuthController:
    """Wire repository -> service -> controller for request scope."""
    repository = AuthRepository(db)
    service = AuthService(repository)
    return AuthController(service)


@router.get("/status", response_model=APIResponse[AuthModuleStatus])
def module_status(
    controller: AuthController = Depends(get_controller),
) -> APIResponse[AuthModuleStatus]:
    """Scaffold endpoint verifying auth router -> controller -> service -> repository wiring."""
    return controller.get_status()