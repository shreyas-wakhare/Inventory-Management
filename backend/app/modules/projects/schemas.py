"""Pydantic v2 request/response schemas for the projects domain."""

from pydantic import BaseModel, ConfigDict


class ProjectModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the projects module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str