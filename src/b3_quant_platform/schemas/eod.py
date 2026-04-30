from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from b3_quant_platform.models.enums import ComparisonVerdict


class MarketSnapshotInput(BaseModel):
    ticker: str
    market: str = "equities"
    open_price: Decimal = Field(..., ge=0)
    high_price: Decimal = Field(..., ge=0)
    low_price: Decimal = Field(..., ge=0)
    close_price: Decimal = Field(..., ge=0)
    adjusted_close: Decimal = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    source_version: str


class MarketSnapshotBatchCreate(BaseModel):
    reference_date: date
    snapshots: list[MarketSnapshotInput]


class MarketSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_date: date
    ticker: str
    market: str
    close_price: Decimal
    adjusted_close: Decimal
    volume: int
    source_version: str
    created_at: datetime


class EodComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    reference_date: date
    ticker: str
    scenario_slug: str
    expected_close: Decimal
    actual_close: Decimal
    tracking_error_bps: Decimal
    verdict: ComparisonVerdict
    comparison_details_json: dict[str, str | float | int]
    created_at: datetime
