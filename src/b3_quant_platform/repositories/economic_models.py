from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from b3_quant_platform.models.entities import (
    AptFactorLoading,
    ArimaForecast,
    CapmMetric,
    FeatureStoreSnapshot,
    GarchVolatility,
    IntrinsicValueEstimate,
    ValuationMetric,
)
from b3_quant_platform.models.enums import EconomicModelName, EconomicModelWindow
from b3_quant_platform.repositories.base import SQLAlchemyRepository


def _filter_portfolio(statement, column, portfolio_id: UUID | None):
    if portfolio_id is None:
        return statement.where(column.is_(None))
    return statement.where(column == portfolio_id)


class EconomicModelsRepository(SQLAlchemyRepository[CapmMetric]):
    model = CapmMetric

    def upsert_capm_metric(
        self,
        *,
        portfolio_id: UUID | None,
        asset_identifier: str,
        market_identifier: str,
        reference_date: date,
        window: EconomicModelWindow,
        risk_free_rate: float,
        alpha: float,
        beta: float,
        expected_return: float,
        actual_return: float,
        r_squared: float,
        residual_volatility: float,
        inputs_json: dict[str, Any],
        explanation_json: dict[str, Any],
        model_state_json: dict[str, Any],
    ) -> CapmMetric:
        statement = select(CapmMetric).where(
            CapmMetric.asset_identifier == asset_identifier,
            CapmMetric.market_identifier == market_identifier,
            CapmMetric.reference_date == reference_date,
            CapmMetric.window == window,
        )
        statement = _filter_portfolio(statement, CapmMetric.portfolio_id, portfolio_id)
        entity = self.session.scalar(statement)
        if entity is None:
            entity = CapmMetric(
                portfolio_id=portfolio_id,
                reference_date=reference_date,
                window=window,
                asset_identifier=asset_identifier,
                market_identifier=market_identifier,
                risk_free_rate=risk_free_rate,
                alpha=alpha,
                beta=beta,
                expected_return=expected_return,
                actual_return=actual_return,
                r_squared=r_squared,
                residual_volatility=residual_volatility,
                inputs_json=inputs_json,
                explanation_json=explanation_json,
                model_state_json=model_state_json,
            )
            return self.add(entity)

        entity.risk_free_rate = risk_free_rate
        entity.alpha = alpha
        entity.beta = beta
        entity.expected_return = expected_return
        entity.actual_return = actual_return
        entity.r_squared = r_squared
        entity.residual_volatility = residual_volatility
        entity.inputs_json = inputs_json
        entity.explanation_json = explanation_json
        entity.model_state_json = model_state_json
        self.session.flush()
        return entity

    def replace_apt_factor_loadings(
        self,
        *,
        portfolio_id: UUID | None,
        asset_identifier: str,
        reference_date: date,
        window: EconomicModelWindow,
        rows: list[dict[str, Any]],
    ) -> list[AptFactorLoading]:
        statement = select(AptFactorLoading).where(
            AptFactorLoading.asset_identifier == asset_identifier,
            AptFactorLoading.reference_date == reference_date,
            AptFactorLoading.window == window,
        )
        statement = _filter_portfolio(statement, AptFactorLoading.portfolio_id, portfolio_id)
        for entity in self.session.scalars(statement).all():
            self.session.delete(entity)
        self.session.flush()
        created: list[AptFactorLoading] = []
        for row in rows:
            entity = AptFactorLoading(
                portfolio_id=portfolio_id,
                reference_date=reference_date,
                window=window,
                asset_identifier=asset_identifier,
                factor_name=row["factor_name"],
                factor_loading=row["factor_loading"],
                factor_premium=row["factor_premium"],
                intercept_alpha=row["intercept_alpha"],
                implied_return=row["implied_return"],
                t_stat=row.get("t_stat"),
                p_value=row.get("p_value"),
                residual_volatility=row["residual_volatility"],
                inputs_json=row["inputs_json"],
                explanation_json=row["explanation_json"],
                model_state_json=row["model_state_json"],
            )
            created.append(self.add(entity))
        return created

    def replace_arima_forecasts(
        self,
        *,
        portfolio_id: UUID | None,
        model_name: EconomicModelName,
        series_name: str,
        reference_date: date,
        window: EconomicModelWindow,
        rows: list[dict[str, Any]],
        order_json: dict[str, Any],
        diagnostics_json: dict[str, Any],
        model_state_json: dict[str, Any],
    ) -> list[ArimaForecast]:
        statement = select(ArimaForecast).where(
            ArimaForecast.model_name == model_name,
            ArimaForecast.series_name == series_name,
            ArimaForecast.reference_date == reference_date,
            ArimaForecast.window == window,
        )
        statement = _filter_portfolio(statement, ArimaForecast.portfolio_id, portfolio_id)
        for entity in self.session.scalars(statement).all():
            self.session.delete(entity)
        self.session.flush()
        created: list[ArimaForecast] = []
        for row in rows:
            entity = ArimaForecast(
                portfolio_id=portfolio_id,
                model_name=model_name,
                window=window,
                series_name=series_name,
                reference_date=reference_date,
                forecast_step=row["forecast_step"],
                predicted_value=row["forecast_mean"],
                lower_ci=row["lower_ci"],
                upper_ci=row["upper_ci"],
                order_json=order_json,
                diagnostics_json=diagnostics_json,
                model_state_json=model_state_json,
            )
            created.append(self.add(entity))
        return created

    def replace_garch_volatility(
        self,
        *,
        portfolio_id: UUID | None,
        model_name: EconomicModelName,
        series_name: str,
        reference_date: date,
        window: EconomicModelWindow,
        rows: list[dict[str, Any]],
        diagnostics_json: dict[str, Any],
        model_state_json: dict[str, Any],
    ) -> list[GarchVolatility]:
        statement = select(GarchVolatility).where(
            GarchVolatility.model_name == model_name,
            GarchVolatility.series_name == series_name,
            GarchVolatility.reference_date == reference_date,
            GarchVolatility.window == window,
        )
        statement = _filter_portfolio(statement, GarchVolatility.portfolio_id, portfolio_id)
        for entity in self.session.scalars(statement).all():
            self.session.delete(entity)
        self.session.flush()
        created: list[GarchVolatility] = []
        persistence = float(diagnostics_json.get("persistence", 0.0))
        leverage_term = float(diagnostics_json.get("leverage_term", 0.0))
        for row in rows:
            entity = GarchVolatility(
                portfolio_id=portfolio_id,
                model_name=model_name,
                window=window,
                series_name=series_name,
                reference_date=reference_date,
                forecast_step=row["forecast_step"],
                conditional_volatility=row["conditional_volatility"],
                variance=row["variance"],
                persistence=persistence,
                leverage_term=leverage_term,
                diagnostics_json=diagnostics_json,
                model_state_json=model_state_json,
            )
            created.append(self.add(entity))
        return created

    def replace_valuation_metrics(
        self,
        *,
        portfolio_id: UUID | None,
        asset_identifier: str,
        reference_date: date,
        window: EconomicModelWindow,
        peer_count: int,
        rows: list[dict[str, Any]],
        inputs_json: dict[str, Any],
        explanation_json: dict[str, Any],
        model_state_json: dict[str, Any],
    ) -> list[ValuationMetric]:
        statement = select(ValuationMetric).where(
            ValuationMetric.asset_identifier == asset_identifier,
            ValuationMetric.reference_date == reference_date,
            ValuationMetric.window == window,
        )
        statement = _filter_portfolio(statement, ValuationMetric.portfolio_id, portfolio_id)
        for entity in self.session.scalars(statement).all():
            self.session.delete(entity)
        self.session.flush()
        created: list[ValuationMetric] = []
        for row in rows:
            entity = ValuationMetric(
                portfolio_id=portfolio_id,
                window=window,
                asset_identifier=asset_identifier,
                reference_date=reference_date,
                metric_name=row["metric_name"],
                applied_multiple=row["applied_multiple"],
                denominator_key=row["denominator_key"],
                denominator_value=row["denominator_value"],
                implied_enterprise_value=row["implied_enterprise_value"],
                implied_equity_value=row["implied_equity_value"],
                intrinsic_value_per_share=row["intrinsic_value_per_share"],
                peer_count=peer_count,
                inputs_json=inputs_json,
                explanation_json=explanation_json,
                model_state_json=model_state_json,
            )
            created.append(self.add(entity))
        return created

    def upsert_intrinsic_value_estimate(
        self,
        *,
        portfolio_id: UUID | None,
        asset_identifier: str,
        reference_date: date,
        window: EconomicModelWindow,
        outputs: dict[str, Any],
        inputs_json: dict[str, Any],
        explanation_json: dict[str, Any],
        model_state_json: dict[str, Any],
    ) -> IntrinsicValueEstimate:
        statement = select(IntrinsicValueEstimate).where(
            IntrinsicValueEstimate.asset_identifier == asset_identifier,
            IntrinsicValueEstimate.reference_date == reference_date,
            IntrinsicValueEstimate.window == window,
        )
        statement = _filter_portfolio(statement, IntrinsicValueEstimate.portfolio_id, portfolio_id)
        entity = self.session.scalar(statement)
        if entity is None:
            entity = IntrinsicValueEstimate(
                portfolio_id=portfolio_id,
                asset_identifier=asset_identifier,
                reference_date=reference_date,
                window=window,
                enterprise_value=outputs["enterprise_value"],
                equity_value=outputs["equity_value"],
                intrinsic_value_per_share=outputs["intrinsic_value_per_share"],
                terminal_value=outputs["terminal_value"],
                terminal_present_value=outputs["terminal_present_value"],
                discount_rate=inputs_json["discount_rate"],
                terminal_growth_rate=inputs_json.get("terminal_growth_rate", 0.0),
                inputs_json=inputs_json,
                explanation_json=explanation_json,
                model_state_json=model_state_json,
            )
            return self.add(entity)

        entity.enterprise_value = outputs["enterprise_value"]
        entity.equity_value = outputs["equity_value"]
        entity.intrinsic_value_per_share = outputs["intrinsic_value_per_share"]
        entity.terminal_value = outputs["terminal_value"]
        entity.terminal_present_value = outputs["terminal_present_value"]
        entity.discount_rate = inputs_json["discount_rate"]
        entity.terminal_growth_rate = inputs_json.get("terminal_growth_rate", 0.0)
        entity.inputs_json = inputs_json
        entity.explanation_json = explanation_json
        entity.model_state_json = model_state_json
        self.session.flush()
        return entity


class FeatureStoreSnapshotRepository(SQLAlchemyRepository[FeatureStoreSnapshot]):
    model = FeatureStoreSnapshot

    def upsert_snapshot(
        self,
        *,
        portfolio_id: UUID | None,
        entity_key: str,
        feature_namespace: str,
        reference_date: date,
        window: EconomicModelWindow,
        source_models_json: list[str],
        features_json: dict[str, Any],
    ) -> FeatureStoreSnapshot:
        entity = self.session.scalar(
            select(FeatureStoreSnapshot).where(
                FeatureStoreSnapshot.entity_key == entity_key,
                FeatureStoreSnapshot.feature_namespace == feature_namespace,
                FeatureStoreSnapshot.reference_date == reference_date,
                FeatureStoreSnapshot.window == window,
            )
        )
        if entity is None:
            entity = FeatureStoreSnapshot(
                portfolio_id=portfolio_id,
                entity_key=entity_key,
                feature_namespace=feature_namespace,
                reference_date=reference_date,
                window=window,
                source_models_json=source_models_json,
                features_json=features_json,
            )
            return self.add(entity)

        entity.portfolio_id = portfolio_id
        entity.source_models_json = source_models_json
        entity.features_json = features_json
        self.session.flush()
        return entity