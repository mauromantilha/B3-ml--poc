from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from b3_quant_platform.models.base import Base, SoftDeleteMixin, TimestampMixin, utcnow
from b3_quant_platform.models.enums import (
    ComparisonVerdict,
    ConstraintType,
    EconomicModelName,
    EconomicModelWindow,
    EventScope,
    EventType,
    JobTarget,
    PortfolioObjective,
    PortfolioStatus,
    RunStatus,
    ScenarioType,
    UserRole,
)
from b3_quant_platform.models.types import JSON_VARIANT


class User(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        Index("ix_users_role_active", "role", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_auth_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), default=UserRole.ANALYST, nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferences_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio_families: Mapped[list[PortfolioFamily]] = relationship(back_populates="owner")
    created_strategies: Mapped[list[PortfolioStrategy]] = relationship(back_populates="created_by")
    owned_portfolios: Mapped[list[PortfolioInstance]] = relationship(back_populates="owner")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")


class PortfolioFamily(TimestampMixin, Base):
    __tablename__ = "portfolio_families"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "slug", name="uq_portfolio_family_owner_slug"),
        Index("ix_portfolio_families_owner_active", "owner_user_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    objective: Mapped[PortfolioObjective] = mapped_column(Enum(PortfolioObjective, native_enum=False), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner: Mapped[User] = relationship(back_populates="portfolio_families")
    strategies: Mapped[list[PortfolioStrategy]] = relationship(back_populates="family")
    portfolio_instances: Mapped[list[PortfolioInstance]] = relationship(back_populates="family")


class PortfolioStrategy(TimestampMixin, Base):
    __tablename__ = "portfolio_strategies"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_portfolio_strategy_slug"),
        Index("ix_portfolio_strategies_family_active", "family_id", "is_active"),
        CheckConstraint("risk_budget_bps >= 0", name="ck_portfolio_strategies_risk_budget_bps"),
        CheckConstraint("version >= 1", name="ck_portfolio_strategies_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("portfolio_families.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    objective: Mapped[PortfolioObjective] = mapped_column(Enum(PortfolioObjective, native_enum=False), nullable=False)
    benchmark_ticker: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_budget_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rebalance_rule: Mapped[dict[str, Any]] = mapped_column("rebalance_rule_json", JSON_VARIANT, nullable=False, default=dict)
    constraints_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_config_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    tags_json: Mapped[list[str]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    family: Mapped[PortfolioFamily] = relationship(back_populates="strategies")
    created_by: Mapped[User | None] = relationship(back_populates="created_strategies")
    constraints: Mapped[list[PortfolioConstraint]] = relationship(back_populates="strategy", cascade="all, delete-orphan")
    portfolios: Mapped[list[PortfolioInstance]] = relationship(back_populates="template")
    models: Mapped[list[ModelRegistry]] = relationship(back_populates="strategy")
    training_runs: Mapped[list[TrainingRun]] = relationship(back_populates="strategy")


class PortfolioConstraint(TimestampMixin, Base):
    __tablename__ = "portfolio_constraints"
    __table_args__ = (
        UniqueConstraint("strategy_id", "constraint_key", "active_from", name="uq_portfolio_constraints_strategy_key_from"),
        Index("ix_portfolio_constraints_strategy_active", "strategy_id", "active_from", "active_to"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("portfolio_strategies.id", ondelete="CASCADE"), nullable=False)
    constraint_key: Mapped[str] = mapped_column(String(80), nullable=False)
    constraint_type: Mapped[ConstraintType] = mapped_column(Enum(ConstraintType, native_enum=False), default=ConstraintType.CUSTOM, nullable=False)
    hard_constraint: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rule_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    active_from: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    strategy: Mapped[PortfolioStrategy] = relationship(back_populates="constraints")


class PortfolioInstance(TimestampMixin, Base):
    __tablename__ = "portfolio_instances"
    __table_args__ = (
        UniqueConstraint("strategy_id", "name", "reference_date", name="uq_portfolio_instance"),
        Index("ix_portfolio_instances_family_date", "portfolio_family_id", "reference_date"),
        Index("ix_portfolio_instances_status_date", "status", "reference_date"),
        CheckConstraint("seed_capital >= 0", name="ck_portfolio_instances_seed_capital"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column("strategy_id", Uuid, ForeignKey("portfolio_strategies.id"), nullable=False)
    family_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_family_id", Uuid, ForeignKey("portfolio_families.id"), nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="BRL", nullable=False)
    seed_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[PortfolioStatus] = mapped_column(Enum(PortfolioStatus, native_enum=False), default=PortfolioStatus.DRAFT, nullable=False)
    mandate_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    notes_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    template: Mapped[PortfolioStrategy] = relationship(back_populates="portfolios")
    family: Mapped[PortfolioFamily | None] = relationship(back_populates="portfolio_instances")
    owner: Mapped[User | None] = relationship(back_populates="owned_portfolios")
    positions: Mapped[list[PortfolioPosition]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    valuations: Mapped[list[PortfolioValuationDaily]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    simulation_runs: Mapped[list[SimulationRun]] = relationship(back_populates="portfolio")
    counterfactual_runs: Mapped[list[CounterfactualRun]] = relationship(back_populates="portfolio")
    prediction_runs: Mapped[list[PredictionRun]] = relationship(back_populates="portfolio")
    capm_metrics: Mapped[list[CapmMetric]] = relationship(back_populates="portfolio")
    apt_factor_loadings: Mapped[list[AptFactorLoading]] = relationship(back_populates="portfolio")
    arima_forecasts: Mapped[list[ArimaForecast]] = relationship(back_populates="portfolio")
    garch_volatility_forecasts: Mapped[list[GarchVolatility]] = relationship(back_populates="portfolio")
    valuation_metrics: Mapped[list[ValuationMetric]] = relationship(back_populates="portfolio")
    intrinsic_value_estimates: Mapped[list[IntrinsicValueEstimate]] = relationship(back_populates="portfolio")
    feature_store_snapshots: Mapped[list[FeatureStoreSnapshot]] = relationship(back_populates="portfolio")
    eod_comparisons: Mapped[list[EodComparison]] = relationship(back_populates="portfolio")


class PortfolioPosition(TimestampMixin, Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (
        UniqueConstraint("portfolio_instance_id", "reference_date", "ticker", name="uq_portfolio_position"),
        Index("ix_portfolio_positions_portfolio_date", "portfolio_instance_id", "reference_date"),
        Index("ix_portfolio_positions_market_ticker_date", "market", "ticker", "reference_date"),
        CheckConstraint("target_weight >= -5 AND target_weight <= 5", name="ck_portfolio_positions_target_weight"),
        CheckConstraint("close_price >= 0", name="ck_portfolio_positions_close_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id", ondelete="CASCADE"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(24), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    signal_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    allocation_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    source_snapshot_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="positions")


class PortfolioValuationDaily(TimestampMixin, Base):
    __tablename__ = "portfolio_valuations_daily"
    __table_args__ = (
        UniqueConstraint("portfolio_instance_id", "reference_date", name="uq_portfolio_valuations_daily"),
        Index("ix_portfolio_valuations_reference_date", "reference_date", "portfolio_instance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id", ondelete="CASCADE"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    pnl_daily: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    valuation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="valuations")


class MarketEodSnapshot(TimestampMixin, Base):
    __tablename__ = "market_eod_snapshots"
    __table_args__ = (
        UniqueConstraint("reference_date", "market", "ticker", name="uq_market_snapshot"),
        Index("ix_market_eod_snapshots_date_ticker", "reference_date", "ticker"),
        Index("ix_market_eod_snapshots_market_date", "market", "reference_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    ticker: Mapped[str] = mapped_column(String(24), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_version: Mapped[str] = mapped_column(String(48), nullable=False)
    ingest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_partition_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)


class EventCatalog(TimestampMixin, Base):
    __tablename__ = "events_catalog"
    __table_args__ = (
        UniqueConstraint("code", name="uq_events_catalog_code"),
        Index("ix_events_catalog_date_type", "event_date", "event_type"),
        Index("ix_events_catalog_scope_active", "scope", "is_active"),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_events_catalog_severity"),
        CheckConstraint("expected_duration_days >= 1", name="ck_events_catalog_expected_duration_days"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_events_catalog_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    scope: Mapped[EventScope] = mapped_column(Enum(EventScope, native_enum=False), default=EventScope.BRASIL, nullable=False)
    scope_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    market_scope: Mapped[str] = mapped_column(String(48), default="b3", nullable=False)
    severity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    expected_duration_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.7500"), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    macro_factors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    asset_mappings: Mapped[list[EventAssetMapping]] = relationship(back_populates="event", cascade="all, delete-orphan")
    impact_profiles: Mapped[list[EventImpactProfile]] = relationship(back_populates="event", cascade="all, delete-orphan")
    scenarios: Mapped[list[EventScenario]] = relationship(back_populates="event")
    counterfactual_runs: Mapped[list[CounterfactualRun]] = relationship(back_populates="event")


class EventAssetMapping(TimestampMixin, Base):
    __tablename__ = "event_asset_mapping"
    __table_args__ = (
        UniqueConstraint("event_id", "asset_identifier", "asset_type", name="uq_event_asset_mapping_event_asset"),
        Index("ix_event_asset_mapping_event_primary", "event_id", "is_primary"),
        CheckConstraint("weight >= 0", name="ck_event_asset_mapping_weight"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events_catalog.id", ondelete="CASCADE"), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    mapping_scope: Mapped[EventScope] = mapped_column(Enum(EventScope, native_enum=False), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0000"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    event: Mapped[EventCatalog] = relationship(back_populates="asset_mappings")


class EventImpactProfile(TimestampMixin, Base):
    __tablename__ = "event_impact_profiles"
    __table_args__ = (
        UniqueConstraint("event_id", "profile_name", name="uq_event_impact_profiles_event_profile"),
        Index("ix_event_impact_profiles_event_confidence", "event_id", "confidence"),
        CheckConstraint("expected_duration_days >= 1", name="ck_event_impact_profiles_expected_duration_days"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_event_impact_profiles_confidence"),
        CheckConstraint("transmission_lag_days >= 0", name="ck_event_impact_profiles_transmission_lag_days"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events_catalog.id", ondelete="CASCADE"), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(80), nullable=False)
    shock_template_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    macro_factors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    expected_duration_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.7500"), nullable=False)
    transmission_lag_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    event: Mapped[EventCatalog] = relationship(back_populates="impact_profiles")
    scenarios: Mapped[list[EventScenario]] = relationship(back_populates="impact_profile")


class EventScenario(TimestampMixin, Base):
    __tablename__ = "event_scenarios"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_event_scenarios_slug"),
        Index("ix_event_scenarios_event_active", "event_id", "active"),
        Index("ix_event_scenarios_scope_active", "scope", "active"),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_event_scenarios_severity"),
        CheckConstraint("expected_duration_days >= 1", name="ck_event_scenarios_expected_duration_days"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_event_scenarios_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("events_catalog.id", ondelete="SET NULL"), nullable=True)
    impact_profile_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("event_impact_profiles.id", ondelete="SET NULL"), nullable=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    scenario_type: Mapped[ScenarioType] = mapped_column(Enum(ScenarioType, native_enum=False), nullable=False)
    scope: Mapped[EventScope] = mapped_column(Enum(EventScope, native_enum=False), default=EventScope.BRASIL, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    expected_duration_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.7500"), nullable=False)
    affected_assets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    macro_factors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    shock_vector_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped[EventCatalog | None] = relationship(back_populates="scenarios")
    impact_profile: Mapped[EventImpactProfile | None] = relationship(back_populates="scenarios")
    simulation_runs: Mapped[list[SimulationRun]] = relationship(back_populates="scenario")
    counterfactual_runs: Mapped[list[CounterfactualRun]] = relationship(back_populates="scenario")


class SimulationRun(TimestampMixin, Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint("event_scenario_id", "portfolio_instance_id", "reference_date", name="uq_simulation_run"),
        Index("ix_simulation_runs_reference_date", "reference_date", "run_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[uuid.UUID] = mapped_column("event_scenario_id", Uuid, ForeignKey("event_scenarios.id"), nullable=False)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RunStatus] = mapped_column("run_status", Enum(RunStatus, native_enum=False), default=RunStatus.PENDING, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    engine_version: Mapped[str] = mapped_column(String(48), default="v1", nullable=False)
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    scenario: Mapped[EventScenario] = relationship(back_populates="simulation_runs")
    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="simulation_runs")


class CounterfactualRun(TimestampMixin, Base):
    __tablename__ = "counterfactual_runs"
    __table_args__ = (
        UniqueConstraint("event_scenario_id", "portfolio_instance_id", "reference_date", name="uq_counterfactual_run"),
        Index("ix_counterfactual_runs_reference_date", "reference_date", "run_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("events_catalog.id", ondelete="SET NULL"), nullable=True)
    scenario_id: Mapped[uuid.UUID] = mapped_column("event_scenario_id", Uuid, ForeignKey("event_scenarios.id"), nullable=False)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RunStatus] = mapped_column("run_status", Enum(RunStatus, native_enum=False), default=RunStatus.PENDING, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    engine_version: Mapped[str] = mapped_column(String(48), default="v1", nullable=False)
    baseline_nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    counterfactual_nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    delta_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    shock_vector_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    event: Mapped[EventCatalog | None] = relationship(back_populates="counterfactual_runs")
    scenario: Mapped[EventScenario] = relationship(back_populates="counterfactual_runs")
    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="counterfactual_runs")


class ModelRegistry(TimestampMixin, Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_registry_name_version"),
        Index("ix_model_registry_active", "active", "framework"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_strategy_id", Uuid, ForeignKey("portfolio_strategies.id"), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    framework: Mapped[str] = mapped_column(String(32), default="tensorflow", nullable=False)
    objective: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    tags_json: Mapped[list[str]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    strategy: Mapped[PortfolioStrategy | None] = relationship(back_populates="models")
    training_runs: Mapped[list[TrainingRun]] = relationship(back_populates="model")
    prediction_runs: Mapped[list[PredictionRun]] = relationship(back_populates="model")


class TrainingRun(TimestampMixin, Base):
    __tablename__ = "training_runs"
    __table_args__ = (
        UniqueConstraint("model_id", "reference_date", "dataset_fingerprint", name="uq_training_runs_dataset_fingerprint"),
        Index("ix_training_runs_reference_date", "reference_date", "run_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("model_registry.id"), nullable=False)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_strategy_id", Uuid, ForeignKey("portfolio_strategies.id"), nullable=True)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    status: Mapped[RunStatus] = mapped_column("run_status", Enum(RunStatus, native_enum=False), default=RunStatus.PENDING, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    artifact_uri: Mapped[str] = mapped_column(String(255), nullable=False)

    model: Mapped[ModelRegistry] = relationship(back_populates="training_runs")
    strategy: Mapped[PortfolioStrategy | None] = relationship(back_populates="training_runs")
    prediction_runs: Mapped[list[PredictionRun]] = relationship(back_populates="training_run")


class PredictionRun(TimestampMixin, Base):
    __tablename__ = "prediction_runs"
    __table_args__ = (
        UniqueConstraint("model_id", "portfolio_instance_id", "reference_date", "horizon_days", name="uq_model_run"),
        Index("ix_prediction_runs_portfolio_reference", "portfolio_instance_id", "reference_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("model_registry.id"), nullable=False)
    training_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("training_runs.id"), nullable=True)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False), default=RunStatus.PENDING, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    predictions_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    model: Mapped[ModelRegistry] = relationship(back_populates="prediction_runs")
    training_run: Mapped[TrainingRun | None] = relationship(back_populates="prediction_runs")
    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="prediction_runs")
    eod_comparisons: Mapped[list[EodComparison]] = relationship(back_populates="prediction_run")


class CapmMetric(TimestampMixin, Base):
    __tablename__ = "capm_metrics"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "asset_identifier",
            "market_identifier",
            "reference_date",
            "window",
            name="uq_capm_metrics_scope",
        ),
        Index("ix_capm_metrics_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), default=EconomicModelName.CAPM, nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    market_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_free_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    alpha: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    expected_return: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_return: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    r_squared: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    residual_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="capm_metrics")


class AptFactorLoading(TimestampMixin, Base):
    __tablename__ = "apt_factor_loadings"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "asset_identifier",
            "factor_name",
            "reference_date",
            "window",
            name="uq_apt_factor_loadings_scope",
        ),
        Index("ix_apt_factor_loadings_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), default=EconomicModelName.APT_MULTIFACTOR, nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    factor_loading: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    factor_premium: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    intercept_alpha: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    implied_return: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    t_stat: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    p_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    residual_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="apt_factor_loadings")


class ArimaForecast(TimestampMixin, Base):
    __tablename__ = "arima_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "series_name",
            "reference_date",
            "window",
            "forecast_step",
            "model_name",
            name="uq_arima_forecasts_scope",
        ),
        Index("ix_arima_forecasts_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    series_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_step: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lower_ci: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    upper_ci: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    order_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="arima_forecasts")


class GarchVolatility(TimestampMixin, Base):
    __tablename__ = "garch_volatility"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "series_name",
            "reference_date",
            "window",
            "forecast_step",
            "model_name",
            name="uq_garch_volatility_scope",
        ),
        Index("ix_garch_volatility_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    series_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_step: Mapped[int] = mapped_column(Integer, nullable=False)
    conditional_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    persistence: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    leverage_term: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="garch_volatility_forecasts")


class ValuationMetric(TimestampMixin, Base):
    __tablename__ = "valuation_metrics"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "asset_identifier",
            "metric_name",
            "reference_date",
            "window",
            name="uq_valuation_metrics_scope",
        ),
        Index("ix_valuation_metrics_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), default=EconomicModelName.MULTIPLES, nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    applied_multiple: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    denominator_key: Mapped[str] = mapped_column(String(64), nullable=False)
    denominator_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    implied_enterprise_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    implied_equity_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    intrinsic_value_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    peer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="valuation_metrics")


class IntrinsicValueEstimate(TimestampMixin, Base):
    __tablename__ = "intrinsic_value_estimates"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_instance_id",
            "asset_identifier",
            "reference_date",
            "window",
            name="uq_intrinsic_value_estimates_scope",
        ),
        Index("ix_intrinsic_value_estimates_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    model_name: Mapped[EconomicModelName] = mapped_column(Enum(EconomicModelName, native_enum=False), default=EconomicModelName.DISCOUNTED_CASH_FLOW, nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    enterprise_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    equity_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    intrinsic_value_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    terminal_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    terminal_present_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    terminal_growth_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    model_state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="intrinsic_value_estimates")


class FeatureStoreSnapshot(TimestampMixin, Base):
    __tablename__ = "feature_store_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "entity_key",
            "feature_namespace",
            "reference_date",
            "window",
            name="uq_feature_store_snapshots_scope",
        ),
        Index("ix_feature_store_snapshots_reference_window", "reference_date", "window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=True)
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    window: Mapped[EconomicModelWindow] = mapped_column(Enum(EconomicModelWindow, native_enum=False), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_models_json: Mapped[list[str]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance | None] = relationship(back_populates="feature_store_snapshots")


class EodComparison(TimestampMixin, Base):
    __tablename__ = "eod_comparisons"
    __table_args__ = (
        UniqueConstraint("portfolio_instance_id", "reference_date", "ticker", "scenario_slug", name="uq_eod_comparison"),
        Index("ix_eod_comparisons_date_portfolio", "reference_date", "portfolio_instance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column("portfolio_instance_id", Uuid, ForeignKey("portfolio_instances.id"), nullable=False)
    prediction_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("prediction_runs.id"), nullable=True)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(24), nullable=False)
    scenario_slug: Mapped[str] = mapped_column(String(80), nullable=False, default="baseline")
    expected_close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tracking_error_bps: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    verdict: Mapped[ComparisonVerdict] = mapped_column(Enum(ComparisonVerdict, native_enum=False), nullable=False)
    comparison_details_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    portfolio: Mapped[PortfolioInstance] = relationship(back_populates="eod_comparisons")
    prediction_run: Mapped[PredictionRun | None] = relationship(back_populates="eod_comparisons")


class SystemJob(TimestampMixin, Base):
    __tablename__ = "system_jobs"
    __table_args__ = (
        UniqueConstraint("job_name", name="uq_system_jobs_job_name"),
        Index("ix_system_jobs_target_active", "service_name", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(120), nullable=False)
    service_name: Mapped[JobTarget] = mapped_column(Enum(JobTarget, native_enum=False), nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_scope: Mapped[str] = mapped_column(String(32), default="reference_date", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    executions: Mapped[list[JobExecution]] = relationship(back_populates="system_job")


class JobExecution(TimestampMixin, Base):
    __tablename__ = "job_executions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_job_run_idempotency_key"),
        Index("ix_job_executions_job_date", "job_name", "reference_date"),
        Index("ix_job_executions_system_job_status", "system_job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    system_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("system_jobs.id"), nullable=True)
    job_name: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    result_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qstash_message_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[Any] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    system_job: Mapped[SystemJob | None] = relationship(back_populates="executions")


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_request", "request_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)

    actor: Mapped[User | None] = relationship(back_populates="audit_logs")


PortfolioTemplate = PortfolioStrategy
ScenarioDefinition = EventScenario
ScenarioRun = SimulationRun
ModelRun = PredictionRun
JobRun = JobExecution
