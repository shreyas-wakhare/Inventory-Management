"""Pydantic v2 request/response schemas for the reconciliation domain."""

from pydantic import BaseModel, ConfigDict


class ReconciliationModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the reconciliation module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str