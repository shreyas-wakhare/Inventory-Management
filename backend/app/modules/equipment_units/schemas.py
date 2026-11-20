"""Pydantic v2 request/response schemas for the equipment_units domain."""

from pydantic import BaseModel, ConfigDict


class EquipmentUnitModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the equipment_units module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str