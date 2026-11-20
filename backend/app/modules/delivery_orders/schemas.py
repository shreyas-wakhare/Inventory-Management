"""Pydantic v2 request/response schemas for the delivery_orders domain."""

from pydantic import BaseModel, ConfigDict


class DeliveryOrderModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the delivery_orders module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str