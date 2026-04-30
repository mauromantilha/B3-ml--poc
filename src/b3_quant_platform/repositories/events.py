from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from b3_quant_platform.models.entities import CounterfactualRun, EventAssetMapping, EventCatalog, EventImpactProfile, EventScenario, SimulationRun
from b3_quant_platform.models.enums import EventScope, EventType, RunStatus, ScenarioType
from b3_quant_platform.repositories.base import SQLAlchemyRepository


class EventCatalogRepository(SQLAlchemyRepository[EventCatalog]):
    model = EventCatalog

    def create_event(
        self,
        *,
        code: str,
        name: str,
        description: str = "",
        event_type: EventType,
        event_date: date,
        scope: EventScope = EventScope.BRASIL,
        expected_duration_days: int = 5,
        confidence: Decimal = Decimal("0.75"),
        market_scope: str = "b3",
        severity: int = 3,
        scope_reference: str | None = None,
        is_synthetic: bool = False,
        source_reference: str | None = None,
        macro_factors_json: list[dict[str, Any]] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> EventCatalog:
        event = EventCatalog(
            code=code,
            name=name,
            description=description or name,
            event_type=event_type,
            event_date=event_date,
            scope=scope,
            scope_reference=scope_reference,
            market_scope=market_scope,
            severity=severity,
            expected_duration_days=expected_duration_days,
            confidence=confidence,
            is_synthetic=is_synthetic,
            source_reference=source_reference,
            macro_factors_json=macro_factors_json or [],
            metadata_json=metadata_json or {},
            is_active=True,
        )
        return self.add(event)


class EventAssetMappingRepository(SQLAlchemyRepository[EventAssetMapping]):
    model = EventAssetMapping

    def create_mapping(
        self,
        *,
        event_id: UUID,
        asset_identifier: str,
        asset_type: str,
        mapping_scope: EventScope,
        weight: Decimal = Decimal("1.0"),
        asset_name: str | None = None,
        sector: str | None = None,
        is_primary: bool = False,
        metadata_json: dict[str, Any] | None = None,
    ) -> EventAssetMapping:
        mapping = EventAssetMapping(
            event_id=event_id,
            asset_identifier=asset_identifier,
            asset_name=asset_name,
            asset_type=asset_type,
            mapping_scope=mapping_scope,
            sector=sector,
            weight=weight,
            is_primary=is_primary,
            metadata_json=metadata_json or {},
        )
        return self.add(mapping)


class EventImpactProfileRepository(SQLAlchemyRepository[EventImpactProfile]):
    model = EventImpactProfile

    def create_profile(
        self,
        *,
        event_id: UUID,
        profile_name: str,
        shock_template_json: dict[str, Any] | None = None,
        macro_factors_json: list[dict[str, Any]] | None = None,
        expected_duration_days: int = 5,
        confidence: Decimal = Decimal("0.75"),
        transmission_lag_days: int = 0,
        metadata_json: dict[str, Any] | None = None,
    ) -> EventImpactProfile:
        profile = EventImpactProfile(
            event_id=event_id,
            profile_name=profile_name,
            shock_template_json=shock_template_json or {},
            macro_factors_json=macro_factors_json or [],
            expected_duration_days=expected_duration_days,
            confidence=confidence,
            transmission_lag_days=transmission_lag_days,
            metadata_json=metadata_json or {},
        )
        return self.add(profile)


class EventScenarioRepository(SQLAlchemyRepository[EventScenario]):
    model = EventScenario

    def create_scenario(
        self,
        *,
        slug: str,
        name: str,
        description: str,
        scenario_type: ScenarioType,
        event_id: UUID | None = None,
        impact_profile_id: UUID | None = None,
        scope: EventScope = EventScope.BRASIL,
        severity: int = 3,
        expected_duration_days: int = 5,
        confidence: Decimal = Decimal("0.75"),
        affected_assets_json: list[dict[str, Any]] | None = None,
        macro_factors_json: list[dict[str, Any]] | None = None,
        shock_vector_json: dict[str, Any] | None = None,
        assumptions_json: dict[str, Any] | None = None,
    ) -> EventScenario:
        scenario = EventScenario(
            event_id=event_id,
            impact_profile_id=impact_profile_id,
            slug=slug,
            name=name,
            description=description,
            scenario_type=scenario_type,
            scope=scope,
            severity=severity,
            expected_duration_days=expected_duration_days,
            confidence=confidence,
            affected_assets_json=affected_assets_json or [],
            macro_factors_json=macro_factors_json or [],
            shock_vector_json=shock_vector_json or {},
            assumptions_json=assumptions_json or {},
            active=True,
        )
        return self.add(scenario)


class SimulationRunRepository(SQLAlchemyRepository[SimulationRun]):
    model = SimulationRun

    def create_run(
        self,
        *,
        scenario_id: UUID,
        portfolio_id: UUID,
        reference_date: date,
        status: RunStatus,
        input_hash: str,
        result_summary_json: dict[str, Any] | None = None,
    ) -> SimulationRun:
        run = SimulationRun(
            scenario_id=scenario_id,
            portfolio_id=portfolio_id,
            reference_date=reference_date,
            status=status,
            input_hash=input_hash,
            result_summary_json=result_summary_json or {},
        )
        return self.add(run)


class CounterfactualRunRepository(SQLAlchemyRepository[CounterfactualRun]):
    model = CounterfactualRun

    def create_run(
        self,
        *,
        scenario_id: UUID,
        portfolio_id: UUID,
        reference_date: date,
        status: RunStatus,
        input_hash: str,
        baseline_nav: Decimal,
        counterfactual_nav: Decimal,
        delta_pnl: Decimal,
        event_id: UUID | None = None,
        shock_vector_json: dict[str, Any] | None = None,
        assumptions_json: dict[str, Any] | None = None,
        result_summary_json: dict[str, Any] | None = None,
    ) -> CounterfactualRun:
        run = CounterfactualRun(
            event_id=event_id,
            scenario_id=scenario_id,
            portfolio_id=portfolio_id,
            reference_date=reference_date,
            status=status,
            input_hash=input_hash,
            baseline_nav=baseline_nav,
            counterfactual_nav=counterfactual_nav,
            delta_pnl=delta_pnl,
            shock_vector_json=shock_vector_json or {},
            assumptions_json=assumptions_json or {},
            result_summary_json=result_summary_json or {},
        )
        return self.add(run)
