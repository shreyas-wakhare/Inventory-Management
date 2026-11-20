"""Pydantic v2 request/response schemas for the users domain."""

from pydantic import BaseModel, ConfigDict


class UserModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the users module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str