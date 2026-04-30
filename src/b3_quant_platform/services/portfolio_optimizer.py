from __future__ import annotations

from statistics import mean
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from b3_quant_platform.models.entities import (
    AptFactorLoading,
    ArimaForecast,
    CapmMetric,
    GarchVolatility,
    IntrinsicValueEstimate,
    PortfolioInstance,
    ValuationMetric,
)
from b3_quant_platform.models.enums import EconomicModelWindow


class PortfolioOptimizerService:
    def build_economic_overlay(
        self,
        session: Session,
        *,
        portfolio_id: UUID,
        reference_date,
        window: EconomicModelWindow,
    ) -> dict[str, Any]:
        portfolio = session.scalar(
            select(PortfolioInstance)
            .options(selectinload(PortfolioInstance.positions))
            .where(PortfolioInstance.id == portfolio_id)
        )
        if portfolio is None:
            raise ValueError("Portfolio not found")

        capm_by_asset = {
            row.asset_identifier: row
            for row in session.scalars(
                select(CapmMetric).where(
                    CapmMetric.portfolio_id == portfolio_id,
                    CapmMetric.reference_date == reference_date,
                    CapmMetric.window == window,
                )
            ).all()
        }
        apt_rows = list(
            session.scalars(
                select(AptFactorLoading).where(
                    AptFactorLoading.portfolio_id == portfolio_id,
                    AptFactorLoading.reference_date == reference_date,
                    AptFactorLoading.window == window,
                )
            ).all()
        )
        apt_implied_return_by_asset: dict[str, float] = {}
        for row in apt_rows:
            apt_implied_return_by_asset[row.asset_identifier] = float(row.implied_return)

        arima_by_series = {
            row.series_name: row
            for row in session.scalars(
                select(ArimaForecast).where(
                    ArimaForecast.portfolio_id == portfolio_id,
                    ArimaForecast.reference_date == reference_date,
                    ArimaForecast.window == window,
                    ArimaForecast.forecast_step == 1,
                )
            ).all()
        }
        garch_by_series = {
            row.series_name: row
            for row in session.scalars(
                select(GarchVolatility).where(
                    GarchVolatility.portfolio_id == portfolio_id,
                    GarchVolatility.reference_date == reference_date,
                    GarchVolatility.window == window,
                    GarchVolatility.forecast_step == 1,
                )
            ).all()
        }
        valuation_rows = list(
            session.scalars(
                select(ValuationMetric).where(
                    ValuationMetric.portfolio_id == portfolio_id,
                    ValuationMetric.reference_date == reference_date,
                    ValuationMetric.window == window,
                )
            ).all()
        )
        valuation_per_share_by_asset: dict[str, float] = {}
        for row in valuation_rows:
            valuation_per_share_by_asset.setdefault(row.asset_identifier, []).append(float(row.intrinsic_value_per_share))
        valuation_per_share_by_asset = {
            asset_identifier: mean(values) for asset_identifier, values in valuation_per_share_by_asset.items()
        }
        dcf_by_asset = {
            row.asset_identifier: float(row.intrinsic_value_per_share)
            for row in session.scalars(
                select(IntrinsicValueEstimate).where(
                    IntrinsicValueEstimate.portfolio_id == portfolio_id,
                    IntrinsicValueEstimate.reference_date == reference_date,
                    IntrinsicValueEstimate.window == window,
                )
            ).all()
        }

        overlay_rows = []
        for position in portfolio.positions:
            ticker = position.ticker
            spot_price = float(position.close_price)
            expected_return_signals = []
            if ticker in capm_by_asset:
                expected_return_signals.append(float(capm_by_asset[ticker].expected_return))
            if ticker in apt_implied_return_by_asset:
                expected_return_signals.append(apt_implied_return_by_asset[ticker])
            if ticker in arima_by_series:
                expected_return_signals.append(float(arima_by_series[ticker].predicted_value))
            expected_return = mean(expected_return_signals) if expected_return_signals else 0.0

            intrinsic_per_share = dcf_by_asset.get(ticker, valuation_per_share_by_asset.get(ticker, spot_price))
            valuation_upside = (intrinsic_per_share / spot_price) - 1.0 if spot_price else 0.0
            volatility = float(garch_by_series[ticker].conditional_volatility) if ticker in garch_by_series else 0.0
            optimizer_score = expected_return + (0.5 * valuation_upside) - volatility
            overlay_rows.append(
                {
                    "ticker": ticker,
                    "spot_price": spot_price,
                    "expected_return": expected_return,
                    "valuation_upside": valuation_upside,
                    "risk_proxy": volatility,
                    "optimizer_score": optimizer_score,
                }
            )

        return {
            "portfolio_id": str(portfolio_id),
            "reference_date": reference_date.isoformat(),
            "window": window.value,
            "asset_count": len(overlay_rows),
            "mean_optimizer_score": mean([row["optimizer_score"] for row in overlay_rows]) if overlay_rows else 0.0,
            "overlays": overlay_rows,
        }