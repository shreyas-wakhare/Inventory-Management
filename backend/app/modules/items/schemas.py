"""Pydantic v2 request/response schemas for the items domain."""

from pydantic import BaseModel, ConfigDict


class ItemModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the items module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str