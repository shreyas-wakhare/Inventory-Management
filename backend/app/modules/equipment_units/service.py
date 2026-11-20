"""Business logic and transaction service layer for the equipment_units domain."""

from app.modules.equipment_units.repository import EquipmentUnitRepository
from app.modules.equipment_units.schemas import EquipmentUnitModuleStatus


class EquipmentUnitService:
    """Orchestrates business rules and atomic transactions for equipment_units."""

    def __init__(self, repository: EquipmentUnitRepository) -> None:
        self.repository = repository

    def get_status(self) -> EquipmentUnitModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return EquipmentUnitModuleStatus(**payload)