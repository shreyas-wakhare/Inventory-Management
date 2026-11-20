"""Pydantic v2 request/response schemas for the auth domain."""

from pydantic import BaseModel, ConfigDict


class AuthModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the auth module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str