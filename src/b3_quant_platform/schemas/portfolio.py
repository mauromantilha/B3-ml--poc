from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from b3_quant_platform.models.enums import PortfolioObjective, PortfolioStatus
from b3_quant_platform.schemas.common import PositionInput


class PortfolioTemplateCreate(BaseModel):
    slug: str | None = None
    name: str
    objective: PortfolioObjective
    benchmark_ticker: str
    risk_budget_bps: int = Field(..., ge=0)
    rebalance_rule: dict[str, str | int | float] = Field(default_factory=dict)
    constraints: dict[str, str | int | float | list[str]] = Field(default_factory=dict)
    model_config: dict[str, str | int | float] = Field(default_factory=dict)


class PortfolioTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    objective: PortfolioObjective
    benchmark_ticker: str
    risk_budget_bps: int
    rebalance_rule: dict[str, str | int | float]
    constraints_json: dict[str, str | int | float | list[str]]
    model_config_json: dict[str, str | int | float]
    created_at: datetime
    updated_at: datetime


class PortfolioInstanceCreate(BaseModel):
    template_id: UUID
    name: str
    reference_date: date
    seed_capital: Decimal = Field(..., ge=0)
    base_currency: str = "BRL"
    status: PortfolioStatus = PortfolioStatus.DRAFT
    mandate: dict[str, str | int | float] = Field(default_factory=dict)
    positions: list[PositionInput] = Field(default_factory=list)


class PortfolioPositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    market: str
    target_weight: Decimal
    quantity: Decimal
    close_price: Decimal
    signal_json: dict[str, float | str]


class PortfolioInstanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    name: str
    reference_date: date
    seed_capital: Decimal
    base_currency: str
    status: PortfolioStatus
    mandate_json: dict[str, str | int | float]
    positions: list[PortfolioPositionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SeedTemplatesResponse(BaseModel):
    created: int
    skipped: int
    templates: list[str]
