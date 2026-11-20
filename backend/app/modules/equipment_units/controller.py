"""HTTP controller layer for the equipment_units domain."""

from app.modules.equipment_units.schemas import EquipmentUnitModuleStatus
from app.modules.equipment_units.service import EquipmentUnitService
from app.shared.schemas import APIResponse


class EquipmentUnitController:
    """Coordinates HTTP request/response mapping for equipment_units routes."""

    def __init__(self, service: EquipmentUnitService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[EquipmentUnitModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)