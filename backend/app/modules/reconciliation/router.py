"""FastAPI router definitions and dependency wiring for the reconciliation domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.reconciliation.controller import ReconciliationController
from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.schemas import ReconciliationModuleStatus
from app.modules.reconciliation.service import ReconciliationService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def get_controller(db: DbSession) -> ReconciliationController:
    """Wire repository -> service -> controller for request scope."""
    repository = ReconciliationRepository(db)
    service = ReconciliationService(repository)
    return ReconciliationController(service)


@router.get("/status", response_model=APIResponse[ReconciliationModuleStatus])
def module_status(
    controller: ReconciliationController = Depends(get_controller),
) -> APIResponse[ReconciliationModuleStatus]:
    """Scaffold endpoint verifying reconciliation router -> controller -> service -> repository wiring."""
    return controller.get_status()