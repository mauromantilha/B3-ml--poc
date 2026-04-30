from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from b3_quant_platform.models.entities import CounterfactualRun, EventCatalog, EventImpactProfile, EventScenario, PortfolioInstance
from b3_quant_platform.models.enums import EventScope, RunStatus
from b3_quant_platform.repositories.events import (
    CounterfactualRunRepository,
    EventAssetMappingRepository,
    EventCatalogRepository,
    EventImpactProfileRepository,
    EventScenarioRepository,
)
from b3_quant_platform.schemas.scenario import (
    CounterfactualRunRequest,
    EventAssetMappingCreate,
    EventCatalogCreate,
    EventImpactProfileCreate,
    EventScenarioFromEventCreate,
)


def apply_shock_vector_to_portfolio(
    portfolio: PortfolioInstance,
    shock_vector: dict[str, Any],
) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
    default_shock = Decimal(str(shock_vector.get("default_price_shock_pct", 0)))
    overrides = shock_vector.get("ticker_overrides", {})

    projected_nav = Decimal(portfolio.seed_capital)
    total_pnl = Decimal("0")
    impacts: list[dict[str, Any]] = []

    for position in portfolio.positions:
        ticker_shock = Decimal(str(overrides.get(position.ticker, default_shock)))
        shocked_price = Decimal(position.close_price) * (Decimal("1") + ticker_shock)
        pnl_delta = (shocked_price - Decimal(position.close_price)) * Decimal(position.quantity)
        projected_nav += pnl_delta
        total_pnl += pnl_delta
        impacts.append(
            {
                "ticker": position.ticker,
                "applied_shock_pct": float(ticker_shock),
                "shocked_price": float(shocked_price),
                "pnl_delta": float(pnl_delta),
            }
        )

    return projected_nav, total_pnl, impacts


class EventCatalogService:
    def list_events(self, session: Session) -> list[EventCatalog]:
        statement = (
            select(EventCatalog)
            .options(
                selectinload(EventCatalog.asset_mappings),
                selectinload(EventCatalog.impact_profiles),
            )
            .order_by(EventCatalog.event_date.desc(), EventCatalog.severity.desc())
        )
        return list(session.scalars(statement).unique().all())

    def get_event(self, session: Session, event_id: UUID) -> EventCatalog | None:
        statement = (
            select(EventCatalog)
            .options(
                selectinload(EventCatalog.asset_mappings),
                selectinload(EventCatalog.impact_profiles),
            )
            .where(EventCatalog.id == event_id)
        )
        return session.scalar(statement)

    def create_event(self, session: Session, payload: EventCatalogCreate) -> EventCatalog:
        existing = session.scalar(select(EventCatalog).where(EventCatalog.code == payload.code))
        if existing is not None:
            return self.get_event(session, existing.id) or existing

        event = EventCatalogRepository(session).create_event(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            event_type=payload.event_type,
            event_date=payload.event_date,
            scope=payload.scope,
            scope_reference=payload.scope_reference,
            market_scope=payload.market_scope,
            severity=payload.severity,
            expected_duration_days=payload.expected_duration_days,
            confidence=payload.confidence,
            is_synthetic=payload.is_synthetic,
            source_reference=payload.source_reference,
            macro_factors_json=[item.model_dump(mode="json") for item in payload.macro_factors],
            metadata_json=payload.metadata,
        )

        mapping_repo = EventAssetMappingRepository(session)
        for mapping in payload.affected_assets:
            mapping_repo.create_mapping(
                event_id=event.id,
                asset_identifier=mapping.asset_identifier,
                asset_name=mapping.asset_name,
                asset_type=mapping.asset_type,
                mapping_scope=mapping.mapping_scope,
                sector=mapping.sector,
                weight=mapping.weight,
                is_primary=mapping.is_primary,
                metadata_json=mapping.metadata,
            )

        session.flush()
        return self.get_event(session, event.id) or event

    def add_asset_mapping(
        self,
        session: Session,
        event_id: UUID,
        payload: EventAssetMappingCreate,
    ) -> Any:
        self._require_event(session, event_id)
        return EventAssetMappingRepository(session).create_mapping(
            event_id=event_id,
            asset_identifier=payload.asset_identifier,
            asset_name=payload.asset_name,
            asset_type=payload.asset_type,
            mapping_scope=payload.mapping_scope,
            sector=payload.sector,
            weight=payload.weight,
            is_primary=payload.is_primary,
            metadata_json=payload.metadata,
        )

    def add_impact_profile(
        self,
        session: Session,
        event_id: UUID,
        payload: EventImpactProfileCreate,
    ) -> EventImpactProfile:
        self._require_event(session, event_id)
        return EventImpactProfileRepository(session).create_profile(
            event_id=event_id,
            profile_name=payload.profile_name,
            shock_template_json=payload.shock_template,
            macro_factors_json=[item.model_dump(mode="json") for item in payload.macro_factors],
            expected_duration_days=payload.expected_duration_days,
            confidence=payload.confidence,
            transmission_lag_days=payload.transmission_lag_days,
            metadata_json=payload.metadata,
        )

    def create_scenario_from_event(self, session: Session, payload: EventScenarioFromEventCreate) -> EventScenario:
        event = self._require_event(session, payload.event_id)
        profile = self._resolve_profile(event, payload.impact_profile_id)
        shock_vector = self.event_to_shock_vector(
            session,
            payload.event_id,
            impact_profile_id=payload.impact_profile_id,
        )
        slug = payload.slug or self._slugify(f"{event.code}-{payload.scenario_type.value}")

        existing = session.scalar(select(EventScenario).where(EventScenario.slug == slug))
        if existing is not None:
            return existing

        scenario = EventScenarioRepository(session).create_scenario(
            event_id=event.id,
            impact_profile_id=profile.id if profile is not None else None,
            slug=slug,
            name=payload.name or event.name,
            description=payload.description or event.description,
            scenario_type=payload.scenario_type,
            scope=event.scope,
            severity=payload.severity or event.severity,
            expected_duration_days=payload.expected_duration_days
            or (profile.expected_duration_days if profile is not None else event.expected_duration_days),
            confidence=payload.confidence or (profile.confidence if profile is not None else event.confidence),
            affected_assets_json=shock_vector["affected_assets"],
            macro_factors_json=shock_vector["macro_factors"],
            shock_vector_json=shock_vector["shock_vector"],
            assumptions_json=payload.assumptions,
        )
        session.flush()
        session.refresh(scenario)
        return scenario

    def event_to_shock_vector(
        self,
        session: Session,
        event_id: UUID,
        *,
        impact_profile_id: UUID | None = None,
    ) -> dict[str, Any]:
        event = self._require_event(session, event_id)
        profile = self._resolve_profile(event, impact_profile_id)
        template = dict(profile.shock_template_json) if profile is not None else {}
        macro_factors = list(profile.macro_factors_json) if profile is not None else list(event.macro_factors_json)
        confidence = profile.confidence if profile is not None else event.confidence
        expected_duration_days = profile.expected_duration_days if profile is not None else event.expected_duration_days

        base_shock = Decimal(str(template.get("default_price_shock_pct", self._default_shock_for_event(event.severity))))
        if event.scope == EventScope.GLOBAL:
            base_shock *= Decimal("1.25")

        shock_vector: dict[str, Any] = {
            "scope": event.scope.value,
            "scope_reference": event.scope_reference,
            "severity": event.severity,
            "confidence": float(confidence),
            "expected_duration_days": expected_duration_days,
            "default_price_shock_pct": float(base_shock if event.scope in {EventScope.BRASIL, EventScope.GLOBAL} else Decimal("0")),
            "ticker_overrides": {},
            "sector_overrides": {},
            "index_overrides": {},
            "macro_factor_shocks": self._serialise_macro_factors(macro_factors),
        }

        affected_assets: list[dict[str, Any]] = []
        for mapping in event.asset_mappings:
            weighted_shock = base_shock * Decimal(mapping.weight)
            affected_assets.append(
                {
                    "asset_identifier": mapping.asset_identifier,
                    "asset_name": mapping.asset_name,
                    "asset_type": mapping.asset_type,
                    "mapping_scope": mapping.mapping_scope.value,
                    "sector": mapping.sector,
                    "weight": float(mapping.weight),
                    "is_primary": mapping.is_primary,
                }
            )
            if event.scope == EventScope.EMPRESA:
                shock_vector["ticker_overrides"][mapping.asset_identifier] = float(weighted_shock)
            elif event.scope == EventScope.SETOR:
                if mapping.sector:
                    shock_vector["sector_overrides"][mapping.sector] = float(weighted_shock)
                shock_vector["ticker_overrides"][mapping.asset_identifier] = float(weighted_shock)
            elif event.scope == EventScope.INDICE and mapping.asset_type == "index":
                shock_vector["index_overrides"][mapping.asset_identifier] = float(weighted_shock)
            else:
                shock_vector["ticker_overrides"][mapping.asset_identifier] = float(weighted_shock)

        for section in ("ticker_overrides", "sector_overrides", "index_overrides"):
            explicit_overrides = template.get(section, {})
            shock_vector[section].update({key: float(value) for key, value in explicit_overrides.items()})

        return {
            "event_id": event.id,
            "scope": event.scope,
            "severity": event.severity,
            "confidence": confidence,
            "expected_duration_days": expected_duration_days,
            "affected_assets": affected_assets,
            "macro_factors": macro_factors,
            "shock_vector": shock_vector,
        }

    def run_counterfactual(self, session: Session, payload: CounterfactualRunRequest) -> CounterfactualRun:
        scenario = session.scalar(
            select(EventScenario)
            .options(selectinload(EventScenario.event))
            .where(EventScenario.slug == payload.scenario_slug)
        )
        if scenario is None:
            raise ValueError("Scenario not found")

        portfolio = session.scalar(
            select(PortfolioInstance)
            .options(selectinload(PortfolioInstance.positions))
            .where(PortfolioInstance.id == payload.portfolio_id)
        )
        if portfolio is None:
            raise ValueError("Portfolio not found")

        existing = session.scalar(
            select(CounterfactualRun).where(
                CounterfactualRun.scenario_id == scenario.id,
                CounterfactualRun.portfolio_id == payload.portfolio_id,
                CounterfactualRun.reference_date == payload.reference_date,
            )
        )
        if existing is not None:
            return existing

        shock_vector = self._apply_counterfactual_assumptions(scenario.shock_vector_json, payload.assumptions)
        counterfactual_nav, aggregate_pnl, impacts = apply_shock_vector_to_portfolio(portfolio, shock_vector)
        baseline_nav = Decimal(portfolio.seed_capital)
        input_hash = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        run = CounterfactualRunRepository(session).create_run(
            event_id=scenario.event_id,
            scenario_id=scenario.id,
            portfolio_id=portfolio.id,
            reference_date=payload.reference_date,
            status=RunStatus.SUCCEEDED,
            input_hash=input_hash,
            baseline_nav=baseline_nav,
            counterfactual_nav=counterfactual_nav,
            delta_pnl=aggregate_pnl,
            shock_vector_json=shock_vector,
            assumptions_json=payload.assumptions,
            result_summary_json={
                "scenario_slug": scenario.slug,
                "baseline_nav": float(baseline_nav),
                "counterfactual_nav": float(counterfactual_nav),
                "aggregate_pnl": float(aggregate_pnl),
                "position_impacts": impacts,
            },
        )
        session.flush()
        session.refresh(run)
        return run

    def _apply_counterfactual_assumptions(
        self,
        shock_vector: dict[str, Any],
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        if not assumptions:
            return dict(shock_vector)
        merged = dict(shock_vector)
        multiplier = Decimal(str(assumptions.get("shock_multiplier", 1)))
        merged["default_price_shock_pct"] = float(Decimal(str(merged.get("default_price_shock_pct", 0))) * multiplier)
        ticker_overrides = {
            key: float(Decimal(str(value)) * multiplier)
            for key, value in merged.get("ticker_overrides", {}).items()
        }
        ticker_overrides.update({key: float(value) for key, value in assumptions.get("ticker_overrides", {}).items()})
        merged["ticker_overrides"] = ticker_overrides
        merged["assumption_overrides"] = assumptions
        return merged

    def _require_event(self, session: Session, event_id: UUID) -> EventCatalog:
        event = self.get_event(session, event_id)
        if event is None:
            raise ValueError("Event not found")
        return event

    def _resolve_profile(
        self,
        event: EventCatalog,
        impact_profile_id: UUID | None,
    ) -> EventImpactProfile | None:
        if impact_profile_id is None:
            return event.impact_profiles[0] if event.impact_profiles else None
        for profile in event.impact_profiles:
            if profile.id == impact_profile_id:
                return profile
        raise ValueError("Impact profile not found for event")

    def _serialise_macro_factors(self, macro_factors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        serialised: dict[str, dict[str, Any]] = {}
        for factor in macro_factors:
            key = str(factor["factor"])
            serialised[key] = {
                inner_key: (float(inner_value) if isinstance(inner_value, Decimal) else inner_value)
                for inner_key, inner_value in factor.items()
                if inner_key != "factor"
            }
        return serialised

    def _default_shock_for_event(self, severity: int) -> Decimal:
        defaults = {
            1: Decimal("-0.01"),
            2: Decimal("-0.03"),
            3: Decimal("-0.05"),
            4: Decimal("-0.08"),
            5: Decimal("-0.12"),
        }
        return defaults[severity]

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")