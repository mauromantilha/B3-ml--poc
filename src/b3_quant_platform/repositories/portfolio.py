from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from b3_quant_platform.models.entities import (
    PortfolioConstraint,
    PortfolioFamily,
    PortfolioInstance,
    PortfolioPosition,
    PortfolioStrategy,
    PortfolioValuationDaily,
)
from b3_quant_platform.models.enums import ConstraintType, PortfolioObjective, PortfolioStatus
from b3_quant_platform.repositories.base import SQLAlchemyRepository


class PortfolioFamilyRepository(SQLAlchemyRepository[PortfolioFamily]):
    model = PortfolioFamily

    def create_family(
        self,
        *,
        owner_user_id: UUID,
        slug: str,
        name: str,
        objective: PortfolioObjective,
        description: str | None = None,
    ) -> PortfolioFamily:
        family = PortfolioFamily(
            owner_user_id=owner_user_id,
            slug=slug,
            name=name,
            objective=objective,
            description=description,
            metadata_json={},
            is_active=True,
        )
        return self.add(family)


class PortfolioStrategyRepository(SQLAlchemyRepository[PortfolioStrategy]):
    model = PortfolioStrategy

    def create_strategy(
        self,
        *,
        family_id: UUID,
        slug: str,
        name: str,
        objective: PortfolioObjective,
        benchmark_ticker: str,
        risk_budget_bps: int,
        rebalance_rule: dict[str, Any],
        model_config_json: dict[str, Any] | None = None,
        created_by_user_id: UUID | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> PortfolioStrategy:
        strategy = PortfolioStrategy(
            family_id=family_id,
            created_by_user_id=created_by_user_id,
            slug=slug,
            name=name,
            objective=objective,
            benchmark_ticker=benchmark_ticker,
            risk_budget_bps=risk_budget_bps,
            rebalance_rule=rebalance_rule,
            constraints_json=constraints or {},
            model_config_json=model_config_json or {},
            tags_json=[],
            is_active=True,
        )
        self.add(strategy)
        if constraints:
            for key, value in constraints.items():
                self.session.add(
                    PortfolioConstraint(
                        strategy_id=strategy.id,
                        constraint_key=key,
                        constraint_type=self._infer_constraint_type(key),
                        hard_constraint=key.startswith(("max_", "min_")),
                        rule_json={"value": value},
                    )
                )
        self.session.flush()
        return strategy

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


class PortfolioInstanceRepository(SQLAlchemyRepository[PortfolioInstance]):
    model = PortfolioInstance

    def create_instance(
        self,
        *,
        template_id: UUID,
        family_id: UUID | None,
        name: str,
        reference_date: date,
        seed_capital: Decimal,
        base_currency: str = "BRL",
        status: PortfolioStatus = PortfolioStatus.DRAFT,
        mandate_json: dict[str, Any] | None = None,
    ) -> PortfolioInstance:
        instance = PortfolioInstance(
            template_id=template_id,
            family_id=family_id,
            name=name,
            reference_date=reference_date,
            seed_capital=seed_capital,
            base_currency=base_currency,
            status=status,
            mandate_json=mandate_json or {},
            notes_json={},
        )
        return self.add(instance)

    def upsert_position(
        self,
        *,
        portfolio_id: UUID,
        reference_date: date,
        ticker: str,
        market: str,
        target_weight: Decimal,
        quantity: Decimal,
        close_price: Decimal,
        signal_json: dict[str, Any] | None = None,
    ) -> PortfolioPosition:
        position = self.session.scalar(
            select(PortfolioPosition).where(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.reference_date == reference_date,
                PortfolioPosition.ticker == ticker,
            )
        )
        if position is None:
            position = PortfolioPosition(
                portfolio_id=portfolio_id,
                reference_date=reference_date,
                ticker=ticker,
                market=market,
                target_weight=target_weight,
                quantity=quantity,
                close_price=close_price,
                signal_json=signal_json or {},
                allocation_metadata_json={},
            )
            return self.add(position)

        position.market = market
        position.target_weight = target_weight
        position.quantity = quantity
        position.close_price = close_price
        position.signal_json = signal_json or {}
        self.session.flush()
        return position

    def upsert_daily_valuation(
        self,
        *,
        portfolio_id: UUID,
        reference_date: date,
        nav: Decimal,
        gross_exposure: Decimal,
        net_exposure: Decimal,
        cash_balance: Decimal,
        pnl_daily: Decimal,
        drawdown_pct: Decimal,
        valuation_json: dict[str, Any] | None = None,
    ) -> PortfolioValuationDaily:
        valuation = self.session.scalar(
            select(PortfolioValuationDaily).where(
                PortfolioValuationDaily.portfolio_id == portfolio_id,
                PortfolioValuationDaily.reference_date == reference_date,
            )
        )
        if valuation is None:
            valuation = PortfolioValuationDaily(
                portfolio_id=portfolio_id,
                reference_date=reference_date,
                nav=nav,
                gross_exposure=gross_exposure,
                net_exposure=net_exposure,
                cash_balance=cash_balance,
                pnl_daily=pnl_daily,
                drawdown_pct=drawdown_pct,
                valuation_json=valuation_json or {},
            )
            return self.add(valuation)

        valuation.nav = nav
        valuation.gross_exposure = gross_exposure
        valuation.net_exposure = net_exposure
        valuation.cash_balance = cash_balance
        valuation.pnl_daily = pnl_daily
        valuation.drawdown_pct = drawdown_pct
        valuation.valuation_json = valuation_json or {}
        self.session.flush()
        return valuation
