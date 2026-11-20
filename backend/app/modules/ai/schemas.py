"""Pydantic v2 request/response schemas for the ai domain."""

from pydantic import BaseModel, ConfigDict


class AIModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the ai module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str