from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PositionInput(BaseModel):
    ticker: str
    market: str = "equities"
    target_weight: Decimal = Field(..., ge=0)
    quantity: Decimal = Field(..., ge=0)
    close_price: Decimal = Field(..., ge=0)
    signal: dict[str, float | str] = Field(default_factory=dict)


class JobRunEnvelope(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_name: str
    reference_date: date
    status: str
    idempotency_key: str
    result_uri: str | None = None
    created_at: datetime


class ApiMessage(BaseModel):
    message: str
