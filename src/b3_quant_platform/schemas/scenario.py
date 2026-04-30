from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from b3_quant_platform.models.enums import EventScope, EventType, MacroFactor, RunStatus, ScenarioType


class MacroFactorShockInput(BaseModel):
    factor: MacroFactor
    shock_bps: Decimal | None = None
    shock_pct: Decimal | None = None
    rationale: str | None = None


class EventAssetMappingCreate(BaseModel):
    asset_identifier: str
    asset_name: str | None = None
    asset_type: str = "equity"
    mapping_scope: EventScope = EventScope.EMPRESA
    sector: str | None = None
    weight: Decimal = Field(default=Decimal("1.0"), ge=0)
    is_primary: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventAssetMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_identifier: str
    asset_name: str | None
    asset_type: str
    mapping_scope: EventScope
    sector: str | None
    weight: Decimal
    is_primary: bool
    metadata_json: dict[str, Any]


class EventImpactProfileCreate(BaseModel):
    profile_name: str
    shock_template: dict[str, Any] = Field(default_factory=dict)
    macro_factors: list[MacroFactorShockInput] = Field(default_factory=list)
    expected_duration_days: int = Field(default=5, ge=1)
    confidence: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    transmission_lag_days: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventImpactProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_name: str
    shock_template_json: dict[str, Any]
    macro_factors_json: list[dict[str, Any]]
    expected_duration_days: int
    confidence: Decimal
    transmission_lag_days: int
    metadata_json: dict[str, Any]


class EventCatalogCreate(BaseModel):
    code: str
    name: str
    description: str
    event_type: EventType
    event_date: date
    scope: EventScope
    scope_reference: str | None = None
    market_scope: str = "b3"
    severity: int = Field(default=3, ge=1, le=5)
    expected_duration_days: int = Field(default=5, ge=1)
    confidence: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    is_synthetic: bool = False
    source_reference: str | None = None
    macro_factors: list[MacroFactorShockInput] = Field(default_factory=list)
    affected_assets: list[EventAssetMappingCreate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str
    event_type: EventType
    event_date: date
    scope: EventScope
    scope_reference: str | None
    market_scope: str
    severity: int
    expected_duration_days: int
    confidence: Decimal
    is_synthetic: bool
    source_reference: str | None
    macro_factors_json: list[dict[str, Any]]
    metadata_json: dict[str, Any]
    is_active: bool
    asset_mappings: list[EventAssetMappingRead] = Field(default_factory=list)
    impact_profiles: list[EventImpactProfileRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EventScenarioFromEventCreate(BaseModel):
    event_id: UUID
    impact_profile_id: UUID | None = None
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    scenario_type: ScenarioType = ScenarioType.EXOGENOUS
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    expected_duration_days: int | None = Field(default=None, ge=1)
    severity: int | None = Field(default=None, ge=1, le=5)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class ScenarioDefinitionCreate(BaseModel):
    slug: str | None = None
    name: str
    description: str
    scenario_type: ScenarioType
    scope: EventScope = EventScope.BRASIL
    severity: int = Field(default=3, ge=1, le=5)
    expected_duration_days: int = Field(default=5, ge=1)
    confidence: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    affected_assets: list[dict[str, Any]] = Field(default_factory=list)
    macro_factors: list[dict[str, Any]] = Field(default_factory=list)
    shock_vector: dict[str, float | dict[str, float]] = Field(default_factory=dict)
    active: bool = True


class ScenarioDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    description: str
    scenario_type: ScenarioType
    scope: EventScope
    severity: int
    expected_duration_days: int
    confidence: Decimal
    affected_assets_json: list[dict[str, Any]]
    macro_factors_json: list[dict[str, Any]]
    shock_vector_json: dict[str, float | dict[str, float]]
    active: bool
    created_at: datetime
    updated_at: datetime


class ShockVectorRead(BaseModel):
    event_id: UUID
    scope: EventScope
    severity: int
    confidence: Decimal
    expected_duration_days: int
    affected_assets: list[dict[str, Any]]
    macro_factors: list[dict[str, Any]]
    shock_vector: dict[str, Any]


class ScenarioRunRequest(BaseModel):
    portfolio_id: UUID
    reference_date: date
    scenario_slug: str


class CounterfactualRunRequest(BaseModel):
    portfolio_id: UUID
    reference_date: date
    scenario_slug: str
    assumptions: dict[str, Any] = Field(default_factory=dict)


class CounterfactualRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID | None
    scenario_id: UUID
    portfolio_id: UUID
    reference_date: date
    status: RunStatus
    baseline_nav: Decimal
    counterfactual_nav: Decimal
    delta_pnl: Decimal
    shock_vector_json: dict[str, Any]
    assumptions_json: dict[str, Any]
    result_summary_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ScenarioPositionImpact(BaseModel):
    ticker: str
    shocked_price: Decimal
    pnl_delta: Decimal


class ScenarioRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scenario_id: UUID
    portfolio_id: UUID
    reference_date: date
    status: RunStatus
    result_summary_json: dict[str, str | float | int | list[dict[str, str | float]]]
    created_at: datetime
    updated_at: datetime
