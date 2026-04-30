from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from b3_quant_platform.models.entities import PortfolioInstance, ScenarioDefinition, ScenarioRun
from b3_quant_platform.models.enums import RunStatus
from b3_quant_platform.schemas.scenario import ScenarioDefinitionCreate, ScenarioRunRequest
from b3_quant_platform.services.event_catalog import apply_shock_vector_to_portfolio


class ScenarioLabService:
    def create_scenario(self, session: Session, payload: ScenarioDefinitionCreate) -> ScenarioDefinition:
        slug = payload.slug or self._slugify(payload.name)
        existing = session.scalar(select(ScenarioDefinition).where(ScenarioDefinition.slug == slug))
        if existing:
            return existing

        scenario = ScenarioDefinition(
            slug=slug,
            name=payload.name,
            description=payload.description,
            scenario_type=payload.scenario_type,
            scope=payload.scope,
            severity=payload.severity,
            expected_duration_days=payload.expected_duration_days,
            confidence=payload.confidence,
            affected_assets_json=payload.affected_assets,
            macro_factors_json=payload.macro_factors,
            shock_vector_json=payload.shock_vector,
            active=payload.active,
        )
        session.add(scenario)
        session.flush()
        session.refresh(scenario)
        return scenario

    def run_scenario(self, session: Session, payload: ScenarioRunRequest) -> ScenarioRun:
        scenario = session.scalar(
            select(ScenarioDefinition).where(ScenarioDefinition.slug == payload.scenario_slug)
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
            select(ScenarioRun).where(
                ScenarioRun.scenario_id == scenario.id,
                ScenarioRun.portfolio_id == payload.portfolio_id,
                ScenarioRun.reference_date == payload.reference_date,
            )
        )
        if existing:
            return existing

        projected_nav, total_pnl, impacts = apply_shock_vector_to_portfolio(
            portfolio,
            scenario.shock_vector_json,
        )

        run = ScenarioRun(
            scenario_id=scenario.id,
            portfolio_id=portfolio.id,
            reference_date=payload.reference_date,
            status=RunStatus.SUCCEEDED,
            result_summary_json={
                "scenario_slug": scenario.slug,
                "projected_nav": float(projected_nav),
                "aggregate_pnl": float(total_pnl),
                "position_impacts": impacts,
            },
        )
        session.add(run)
        session.flush()
        session.refresh(run)
        return run

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
