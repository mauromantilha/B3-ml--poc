from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from b3_quant_platform.models.enums import EconomicModelName, EconomicModelWindow


class CapmModelRequest(BaseModel):
    asset_identifier: str
    market_identifier: str = "IBOV"
    asset_returns: list[float]
    market_returns: list[float]
    risk_free_rate: list[float] | float = 0.0
    forecast_market_return: float | None = None
    forecast_risk_free_rate: float | None = None

    @model_validator(mode="after")
    def validate_lengths(self) -> "CapmModelRequest":
        if len(self.asset_returns) != len(self.market_returns):
            raise ValueError("asset_returns and market_returns must have the same length")
        if isinstance(self.risk_free_rate, list) and len(self.risk_free_rate) != len(self.asset_returns):
            raise ValueError("risk_free_rate list must have the same length as asset_returns")
        return self


class AptModelRequest(BaseModel):
    asset_identifier: str
    asset_returns: list[float]
    factor_returns: dict[str, list[float]]
    factor_projection: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lengths(self) -> "AptModelRequest":
        asset_length = len(self.asset_returns)
        if not self.factor_returns:
            raise ValueError("factor_returns cannot be empty")
        for factor_name, values in self.factor_returns.items():
            if len(values) != asset_length:
                raise ValueError(f"factor {factor_name} must have the same length as asset_returns")
        return self


class ArimaModelRequest(BaseModel):
    series_name: str
    time_series: list[float]
    order: tuple[int, int, int] = (1, 0, 0)
    seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0)
    forecast_horizon: int = Field(default=5, ge=1, le=60)
    alpha: float = Field(default=0.05, gt=0, lt=1)


class GarchModelRequest(BaseModel):
    series_name: str
    returns: list[float]
    model_family: EconomicModelName = EconomicModelName.GARCH
    p_order: int = Field(default=1, ge=1, le=3)
    q_order: int = Field(default=1, ge=1, le=3)
    forecast_horizon: int = Field(default=5, ge=1, le=60)
    distribution: str = "normal"

    @model_validator(mode="after")
    def validate_family(self) -> "GarchModelRequest":
        if self.model_family not in {EconomicModelName.GARCH, EconomicModelName.EGARCH}:
            raise ValueError("model_family must be garch or egarch")
        return self


class ComparableMultipleInput(BaseModel):
    ev_ebitda: float | None = None
    ev_sales: float | None = None
    pe: float | None = None
    pb: float | None = None


class RelativeValuationRequest(BaseModel):
    asset_identifier: str
    comparables: list[ComparableMultipleInput]
    fundamentals: dict[str, float]
    net_debt: float = 0.0
    shares_outstanding: float = Field(default=1.0, gt=0)


class DiscountedCashFlowRequest(BaseModel):
    asset_identifier: str
    projected_cash_flows: list[float]
    discount_rate: float = Field(..., gt=0)
    terminal_growth_rate: float = Field(default=0.02, ge=0)
    net_debt: float = 0.0
    shares_outstanding: float = Field(default=1.0, gt=0)


class EconomicModelsJobRequest(BaseModel):
    reference_date: date
    portfolio_id: UUID | None = None
    window: EconomicModelWindow = EconomicModelWindow.SHORT_TERM
    persist_feature_store: bool = True
    run_models: list[EconomicModelName] = Field(default_factory=list)
    capm: CapmModelRequest | None = None
    apt: AptModelRequest | None = None
    arima: ArimaModelRequest | None = None
    garch: GarchModelRequest | None = None
    multiples: RelativeValuationRequest | None = None
    dcf: DiscountedCashFlowRequest | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "EconomicModelsJobRequest":
        if not any([self.capm, self.apt, self.arima, self.garch, self.multiples, self.dcf]):
            raise ValueError("at least one model input section must be provided")
        return self


class EconomicModelsJobResult(BaseModel):
    reference_date: date
    window: EconomicModelWindow
    models_run: list[str]
    output_counts: dict[str, int]
    feature_store_snapshot_id: UUID | None = None
    portfolio_optimizer_overlay: dict[str, Any] | None = None
    details: dict[str, Any] = Field(default_factory=dict)