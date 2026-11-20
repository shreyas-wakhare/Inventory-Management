"""Pydantic v2 request/response schemas for the collection_orders domain."""

from pydantic import BaseModel, ConfigDict


class CollectionOrderModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the collection_orders module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str