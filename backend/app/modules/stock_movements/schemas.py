"""Pydantic v2 request/response schemas for the stock_movements domain."""

from pydantic import BaseModel, ConfigDict


class StockMovementModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the stock_movements module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str