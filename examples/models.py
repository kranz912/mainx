from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WeatherForecastResponse(BaseModel):
    latitude: float
    longitude: float


class StockQuoteResponse(BaseModel):
    quoteResponse: dict[str, Any]
