from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from b3_quant_platform.models.entities import (
    PortfolioConstraint,
    PortfolioFamily,
    PortfolioInstance,
    PortfolioPosition,
    PortfolioTemplate,
    User,
)
from b3_quant_platform.models.enums import ConstraintType, PortfolioObjective, PortfolioStatus, UserRole
from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate, PortfolioTemplateCreate

DEFAULT_SYSTEM_USER_EMAIL = "system@b3quant.local"
DEFAULT_PORTFOLIO_FAMILY_SLUG = "multi-portfolio-factory"

DEFAULT_PORTFOLIO_TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "dividend-income",
        "name": "Dividend Income Brazil",
        "objective": PortfolioObjective.INCOME,
        "benchmark_ticker": "IDIV",
        "risk_budget_bps": 450,
        "rebalance_rule": {"cadence": "monthly", "trigger": "yield-spread"},
        "constraints": {"max_single_name": 0.12, "min_dividend_yield": 0.05},
        "model_config": {"label": "yield_stability", "horizon_days": 5},
    },
    {
        "slug": "factor-momentum",
        "name": "Factor Momentum Brazil",
        "objective": PortfolioObjective.FACTOR,
        "benchmark_ticker": "IBOV",
        "risk_budget_bps": 650,
        "rebalance_rule": {"cadence": "weekly", "trigger": "relative-strength"},
        "constraints": {"max_turnover": 0.18, "min_liquidity_brl": 10000000},
        "model_config": {"label": "momentum_alpha", "horizon_days": 5},
    },
    {
        "slug": "low-vol-defensive",
        "name": "Low Vol Defensive Brazil",
        "objective": PortfolioObjective.DEFENSIVE,
        "benchmark_ticker": "IBOV",
        "risk_budget_bps": 300,
        "rebalance_rule": {"cadence": "monthly", "trigger": "volatility-regime"},
        "constraints": {"max_beta": 0.85, "sector_cap": 0.28},
        "model_config": {"label": "drawdown_control", "horizon_days": 5},
    },
    {
        "slug": "macro-hedge",
        "name": "Macro Hedge Overlay",
        "objective": PortfolioObjective.HEDGE,
        "benchmark_ticker": "DOL1!",
        "risk_budget_bps": 250,
        "rebalance_rule": {"cadence": "event-driven", "trigger": "macro-shock"},
        "constraints": {"max_net_exposure": 0.35, "max_gross_exposure": 1.2},
        "model_config": {"label": "macro_overlay", "horizon_days": 1},
    },
]


class PortfolioFactoryService:
    def seed_default_templates(self, session: Session) -> tuple[int, int, list[str]]:
        created = 0
        skipped = 0
        names: list[str] = []
        system_user = self._get_or_create_system_user(session)
        default_family = self._get_or_create_default_family(session, system_user.id)

        for template_data in DEFAULT_PORTFOLIO_TEMPLATES:
            existing = session.scalar(
                select(PortfolioTemplate).where(PortfolioTemplate.slug == template_data["slug"])
            )
            if existing:
                self._sync_constraints(session, existing.id, template_data["constraints"])
                skipped += 1
                names.append(existing.slug)
                continue

            template = PortfolioTemplate(
                family_id=default_family.id,
                created_by_user_id=system_user.id,
                slug=template_data["slug"],
                name=template_data["name"],
                objective=template_data["objective"],
                benchmark_ticker=template_data["benchmark_ticker"],
                risk_budget_bps=template_data["risk_budget_bps"],
                rebalance_rule=template_data["rebalance_rule"],
                constraints_json=template_data["constraints"],
                model_config_json=template_data["model_config"],
            )
            session.add(template)
            session.flush()
            self._sync_constraints(session, template.id, template_data["constraints"])
            created += 1
            names.append(template_data["slug"])

        session.flush()
        return created, skipped, names

    def list_templates(self, session: Session) -> list[PortfolioTemplate]:
        statement = select(PortfolioTemplate).order_by(PortfolioTemplate.name.asc())
        return list(session.scalars(statement).all())

    def create_template(self, session: Session, payload: PortfolioTemplateCreate) -> PortfolioTemplate:
        slug = payload.slug or self._slugify(payload.name)
        existing = session.scalar(select(PortfolioTemplate).where(PortfolioTemplate.slug == slug))
        if existing:
            return existing

        system_user = self._get_or_create_system_user(session)
        default_family = self._get_or_create_default_family(session, system_user.id)

        template = PortfolioTemplate(
            family_id=default_family.id,
            created_by_user_id=system_user.id,
            slug=slug,
            name=payload.name,
            objective=payload.objective,
            benchmark_ticker=payload.benchmark_ticker,
            risk_budget_bps=payload.risk_budget_bps,
            rebalance_rule=payload.rebalance_rule,
            constraints_json=payload.constraints,
            model_config_json=payload.model_config,
        )
        session.add(template)
        session.flush()
        self._sync_constraints(session, template.id, payload.constraints)
        session.refresh(template)
        return template

    def create_instance(self, session: Session, payload: PortfolioInstanceCreate) -> PortfolioInstance:
        template = session.get(PortfolioTemplate, payload.template_id)
        if template is None:
            raise ValueError("Portfolio template not found")

        instance = PortfolioInstance(
            template_id=payload.template_id,
            family_id=template.family_id,
            name=payload.name,
            reference_date=payload.reference_date,
            base_currency=payload.base_currency,
            seed_capital=payload.seed_capital,
            status=payload.status,
            mandate_json=payload.mandate,
        )
        session.add(instance)
        session.flush()

        for position in payload.positions:
            session.add(
                PortfolioPosition(
                    portfolio_id=instance.id,
                    reference_date=payload.reference_date,
                    ticker=position.ticker,
                    market=position.market,
                    target_weight=position.target_weight,
                    quantity=position.quantity,
                    close_price=position.close_price,
                    signal_json=position.signal,
                )
            )

        session.flush()
        return self.get_instance(session, instance.id)

    def get_instance(self, session: Session, portfolio_id: UUID) -> PortfolioInstance:
        statement = (
            select(PortfolioInstance)
            .options(selectinload(PortfolioInstance.positions))
            .where(PortfolioInstance.id == portfolio_id)
        )
        portfolio = session.scalar(statement)
        if portfolio is None:
            raise ValueError("Portfolio instance not found")
        return portfolio

    def list_portfolios(self, session: Session) -> list[PortfolioInstance]:
        statement = select(PortfolioInstance).options(selectinload(PortfolioInstance.positions))
        return list(session.scalars(statement).all())

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def _get_or_create_system_user(self, session: Session) -> User:
        existing = session.scalar(select(User).where(User.email == DEFAULT_SYSTEM_USER_EMAIL))
        if existing is not None:
            return existing

        user = User(
            email=DEFAULT_SYSTEM_USER_EMAIL,
            full_name="B3 Quant Platform System",
            role=UserRole.SERVICE,
            timezone_name="UTC",
            preferences_json={"seeded_by": "portfolio_factory"},
        )
        session.add(user)
        session.flush()
        return user

    def _get_or_create_default_family(self, session: Session, owner_user_id) -> PortfolioFamily:
        existing = session.scalar(
            select(PortfolioFamily).where(
                PortfolioFamily.owner_user_id == owner_user_id,
                PortfolioFamily.slug == DEFAULT_PORTFOLIO_FAMILY_SLUG,
            )
        )
        if existing is not None:
            return existing

        family = PortfolioFamily(
            owner_user_id=owner_user_id,
            slug=DEFAULT_PORTFOLIO_FAMILY_SLUG,
            name="Multi Portfolio Factory",
            objective=PortfolioObjective.GROWTH,
            description="Família sistêmica para estratégias seed e bootstrap operacional.",
            metadata_json={"managed_by": "portfolio_factory"},
            is_active=True,
        )
        session.add(family)
        session.flush()
        return family

    def _sync_constraints(
        self,
        session: Session,
        strategy_id,
        constraints: dict[str, Any],
    ) -> None:
        existing = {
            row.constraint_key: row
            for row in session.scalars(
                select(PortfolioConstraint).where(PortfolioConstraint.strategy_id == strategy_id)
            ).all()
        }
        for key, raw_value in constraints.items():
            constraint = existing.get(key)
            payload = {"value": raw_value}
            if constraint is None:
                session.add(
                    PortfolioConstraint(
                        strategy_id=strategy_id,
                        constraint_key=key,
                        constraint_type=self._infer_constraint_type(key),
                        hard_constraint=key.startswith(("max_", "min_")),
                        rule_json=payload,
                    )
                )
                continue

            constraint.constraint_type = self._infer_constraint_type(key)
            constraint.hard_constraint = key.startswith(("max_", "min_"))
            constraint.rule_json = payload

    @staticmethod
    def _infer_constraint_type(key: str) -> ConstraintType:
        lowered = key.lower()
        if "liquidity" in lowered:
            return ConstraintType.LIQUIDITY
        if "exposure" in lowered or "beta" in lowered:
            return ConstraintType.EXPOSURE
        if lowered.startswith(("max_", "min_")):
            return ConstraintType.HARD_LIMIT
        return ConstraintType.CUSTOM
