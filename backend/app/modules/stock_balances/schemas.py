"""Pydantic v2 request/response schemas for the stock_balances domain."""

from pydantic import BaseModel, ConfigDict


class StockBalanceModuleStatus(BaseModel):
    """Scaffold status payload confirming layered wiring for the stock_balances module."""

    model_config = ConfigDict(from_attributes=True)

    module: str
    status: str
    message: str