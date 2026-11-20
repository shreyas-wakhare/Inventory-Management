"""FastAPI router definitions and dependency wiring for the equipment_units domain."""

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession
from app.modules.equipment_units.controller import EquipmentUnitController
from app.modules.equipment_units.repository import EquipmentUnitRepository
from app.modules.equipment_units.schemas import EquipmentUnitModuleStatus
from app.modules.equipment_units.service import EquipmentUnitService
from app.shared.schemas import APIResponse

router = APIRouter(prefix="/equipment-units", tags=["equipment-units"])


def get_controller(db: DbSession) -> EquipmentUnitController:
    """Wire repository -> service -> controller for request scope."""
    repository = EquipmentUnitRepository(db)
    service = EquipmentUnitService(repository)
    return EquipmentUnitController(service)


@router.get("/status", response_model=APIResponse[EquipmentUnitModuleStatus])
def module_status(
    controller: EquipmentUnitController = Depends(get_controller),
) -> APIResponse[EquipmentUnitModuleStatus]:
    """Scaffold endpoint verifying equipment_units router -> controller -> service -> repository wiring."""
    return controller.get_status()