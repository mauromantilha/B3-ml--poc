from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from b3_quant_platform.economic_models_engine import (
    AptMultiFactorModel,
    ArimaSarimaModel,
    CapmModel,
    DiscountedCashFlowModel,
    GarchEgarchModel,
    RelativeValuationModel,
)
from b3_quant_platform.models.enums import EconomicModelName
from b3_quant_platform.repositories.economic_models import EconomicModelsRepository
from b3_quant_platform.schemas.economic_models import EconomicModelsJobRequest, EconomicModelsJobResult
from b3_quant_platform.services.feature_store import FeatureStoreService
from b3_quant_platform.services.portfolio_optimizer import PortfolioOptimizerService


class EconomicModelsEngineService:
    def __init__(
        self,
        *,
        feature_store_service: FeatureStoreService | None = None,
        portfolio_optimizer_service: PortfolioOptimizerService | None = None,
    ) -> None:
        self.feature_store_service = feature_store_service or FeatureStoreService()
        self.portfolio_optimizer_service = portfolio_optimizer_service or PortfolioOptimizerService()

    def run(self, session: Session, payload: EconomicModelsJobRequest) -> EconomicModelsJobResult:
        repository = EconomicModelsRepository(session)
        models_run: list[str] = []
        output_counts = {
            "capm_metrics": 0,
            "apt_factor_loadings": 0,
            "arima_forecasts": 0,
            "garch_volatility": 0,
            "valuation_metrics": 0,
            "intrinsic_value_estimates": 0,
        }
        details: dict[str, Any] = {}

        if payload.capm is not None and self._should_run(payload, EconomicModelName.CAPM):
            capm_inputs = payload.capm.model_dump(mode="json")
            model = CapmModel(window=payload.window)
            fit_result = model.fit(capm_inputs)
            prediction = model.predict(capm_inputs)
            entity = repository.upsert_capm_metric(
                portfolio_id=payload.portfolio_id,
                asset_identifier=payload.capm.asset_identifier,
                market_identifier=payload.capm.market_identifier,
                reference_date=payload.reference_date,
                window=payload.window,
                risk_free_rate=self._risk_free_rate_average(payload.capm.risk_free_rate),
                alpha=fit_result.parameters["alpha"],
                beta=fit_result.parameters["beta"],
                expected_return=prediction.outputs["expected_return"],
                actual_return=mean(payload.capm.asset_returns),
                r_squared=fit_result.diagnostics["r_squared"],
                residual_volatility=fit_result.diagnostics["residual_volatility"],
                inputs_json=capm_inputs,
                explanation_json=model.explain(),
                model_state_json=model.serialize(),
            )
            models_run.append(model.model_name.value)
            output_counts["capm_metrics"] = 1
            details["capm"] = {
                "metric_id": str(entity.id),
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        if payload.apt is not None and self._should_run(payload, EconomicModelName.APT_MULTIFACTOR):
            apt_inputs = payload.apt.model_dump(mode="json")
            model = AptMultiFactorModel(window=payload.window)
            fit_result = model.fit(apt_inputs)
            prediction = model.predict(apt_inputs)
            rows = []
            for factor_name, factor_loading in fit_result.parameters["factor_loadings"].items():
                rows.append(
                    {
                        "factor_name": factor_name,
                        "factor_loading": factor_loading,
                        "factor_premium": fit_result.parameters["factor_premia"][factor_name],
                        "intercept_alpha": fit_result.parameters["alpha"],
                        "implied_return": prediction.outputs["expected_return"],
                        "t_stat": fit_result.diagnostics["factor_t_stats"].get(factor_name),
                        "p_value": None,
                        "residual_volatility": fit_result.diagnostics["residual_volatility"],
                        "inputs_json": apt_inputs,
                        "explanation_json": model.explain(),
                        "model_state_json": model.serialize(),
                    }
                )
            entities = repository.replace_apt_factor_loadings(
                portfolio_id=payload.portfolio_id,
                asset_identifier=payload.apt.asset_identifier,
                reference_date=payload.reference_date,
                window=payload.window,
                rows=rows,
            )
            models_run.append(model.model_name.value)
            output_counts["apt_factor_loadings"] = len(entities)
            details["apt"] = {
                "row_ids": [str(entity.id) for entity in entities],
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        if payload.arima is not None and self._should_run(
            payload,
            EconomicModelName.ARIMA,
            EconomicModelName.SARIMA,
        ):
            arima_inputs = payload.arima.model_dump(mode="json")
            model = ArimaSarimaModel(window=payload.window)
            fit_result = model.fit(arima_inputs)
            prediction = model.predict(arima_inputs)
            entities = repository.replace_arima_forecasts(
                portfolio_id=payload.portfolio_id,
                model_name=model.model_name,
                series_name=payload.arima.series_name,
                reference_date=payload.reference_date,
                window=payload.window,
                rows=prediction.outputs["forecasts"],
                order_json={
                    "order": fit_result.parameters["order"],
                    "seasonal_order": fit_result.parameters["seasonal_order"],
                },
                diagnostics_json=fit_result.diagnostics,
                model_state_json=model.serialize(),
            )
            models_run.append(model.model_name.value)
            output_counts["arima_forecasts"] = len(entities)
            details["arima"] = {
                "row_ids": [str(entity.id) for entity in entities],
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        if payload.garch is not None and self._should_run(payload, payload.garch.model_family):
            garch_inputs = payload.garch.model_dump(mode="json")
            model = GarchEgarchModel(window=payload.window)
            fit_result = model.fit(garch_inputs)
            prediction = model.predict(garch_inputs)
            entities = repository.replace_garch_volatility(
                portfolio_id=payload.portfolio_id,
                model_name=model.model_name,
                series_name=payload.garch.series_name,
                reference_date=payload.reference_date,
                window=payload.window,
                rows=prediction.outputs["volatility_forecast"],
                diagnostics_json=fit_result.diagnostics,
                model_state_json=model.serialize(),
            )
            models_run.append(model.model_name.value)
            output_counts["garch_volatility"] = len(entities)
            details["garch"] = {
                "row_ids": [str(entity.id) for entity in entities],
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        if payload.multiples is not None and self._should_run(payload, EconomicModelName.MULTIPLES):
            multiples_inputs = payload.multiples.model_dump(mode="json")
            multiples_inputs["comparables"] = [
                comparable.model_dump(mode="json", exclude_none=True) for comparable in payload.multiples.comparables
            ]
            model = RelativeValuationModel(window=payload.window)
            fit_result = model.fit(multiples_inputs)
            prediction = model.predict(multiples_inputs)
            entities = repository.replace_valuation_metrics(
                portfolio_id=payload.portfolio_id,
                asset_identifier=payload.multiples.asset_identifier,
                reference_date=payload.reference_date,
                window=payload.window,
                peer_count=fit_result.diagnostics["peer_count"],
                rows=prediction.outputs["valuation_rows"],
                inputs_json=multiples_inputs,
                explanation_json=model.explain(),
                model_state_json=model.serialize(),
            )
            models_run.append(model.model_name.value)
            output_counts["valuation_metrics"] = len(entities)
            details["multiples"] = {
                "row_ids": [str(entity.id) for entity in entities],
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        if payload.dcf is not None and self._should_run(payload, EconomicModelName.DISCOUNTED_CASH_FLOW):
            dcf_inputs = payload.dcf.model_dump(mode="json")
            model = DiscountedCashFlowModel(window=payload.window)
            fit_result = model.fit(dcf_inputs)
            prediction = model.predict(dcf_inputs)
            entity = repository.upsert_intrinsic_value_estimate(
                portfolio_id=payload.portfolio_id,
                asset_identifier=payload.dcf.asset_identifier,
                reference_date=payload.reference_date,
                window=payload.window,
                outputs=prediction.outputs,
                inputs_json=dcf_inputs,
                explanation_json=model.explain(),
                model_state_json=model.serialize(),
            )
            models_run.append(model.model_name.value)
            output_counts["intrinsic_value_estimates"] = 1
            details["dcf"] = {
                "estimate_id": str(entity.id),
                "fit": fit_result.to_dict(),
                "prediction": prediction.to_dict(),
            }

        feature_store_snapshot_id = None
        if payload.persist_feature_store:
            features_json = self._build_feature_payload(details)
            snapshot = self.feature_store_service.upsert_economic_features(
                session,
                portfolio_id=payload.portfolio_id,
                entity_key=self._resolve_entity_key(payload),
                reference_date=payload.reference_date,
                window=payload.window,
                features_json=features_json,
                source_models=models_run,
            )
            feature_store_snapshot_id = snapshot.id

        portfolio_optimizer_overlay = None
        if payload.portfolio_id is not None:
            portfolio_optimizer_overlay = self.portfolio_optimizer_service.build_economic_overlay(
                session,
                portfolio_id=payload.portfolio_id,
                reference_date=payload.reference_date,
                window=payload.window,
            )

        return EconomicModelsJobResult(
            reference_date=payload.reference_date,
            window=payload.window,
            models_run=models_run,
            output_counts=output_counts,
            feature_store_snapshot_id=feature_store_snapshot_id,
            portfolio_optimizer_overlay=portfolio_optimizer_overlay,
            details=details,
        )

    @staticmethod
    def _should_run(payload: EconomicModelsJobRequest, *model_names: EconomicModelName) -> bool:
        return not payload.run_models or any(model_name in payload.run_models for model_name in model_names)

    @staticmethod
    def _risk_free_rate_average(risk_free_rate: list[float] | float) -> float:
        if isinstance(risk_free_rate, list):
            return mean(risk_free_rate)
        return float(risk_free_rate)

    @staticmethod
    def _resolve_entity_key(payload: EconomicModelsJobRequest) -> str:
        if payload.portfolio_id is not None:
            return f"portfolio:{payload.portfolio_id}"
        for section in (payload.capm, payload.apt, payload.multiples, payload.dcf):
            if section is not None and hasattr(section, "asset_identifier"):
                return f"asset:{section.asset_identifier}"
        if payload.arima is not None:
            return f"series:{payload.arima.series_name}"
        if payload.garch is not None:
            return f"series:{payload.garch.series_name}"
        return f"reference:{payload.reference_date.isoformat()}"

    @staticmethod
    def _build_feature_payload(details: dict[str, Any]) -> dict[str, Any]:
        features: dict[str, Any] = {}
        capm_prediction = details.get("capm", {}).get("prediction", {}).get("outputs", {})
        if capm_prediction:
            features["capm_expected_return"] = capm_prediction.get("expected_return")
            features["capm_alpha"] = capm_prediction.get("alpha")
            features["capm_beta"] = capm_prediction.get("beta")
        apt_prediction = details.get("apt", {}).get("prediction", {}).get("outputs", {})
        if apt_prediction:
            features["apt_expected_return"] = apt_prediction.get("expected_return")
            for factor_name, contribution in apt_prediction.get("factor_contributions", {}).items():
                features[f"apt_contribution_{factor_name}"] = contribution
        arima_prediction = details.get("arima", {}).get("prediction", {}).get("outputs", {})
        if arima_prediction.get("forecasts"):
            features["arima_forecast_step_1"] = arima_prediction["forecasts"][0]["forecast_mean"]
        garch_prediction = details.get("garch", {}).get("prediction", {}).get("outputs", {})
        if garch_prediction.get("volatility_forecast"):
            features["garch_volatility_step_1"] = garch_prediction["volatility_forecast"][0]["conditional_volatility"]
            features["garch_persistence"] = garch_prediction.get("persistence")
        multiples_prediction = details.get("multiples", {}).get("prediction", {}).get("outputs", {})
        if multiples_prediction.get("aggregate"):
            features["multiples_intrinsic_value_per_share"] = multiples_prediction["aggregate"].get("intrinsic_value_per_share")
        dcf_prediction = details.get("dcf", {}).get("prediction", {}).get("outputs", {})
        if dcf_prediction:
            features["dcf_intrinsic_value_per_share"] = dcf_prediction.get("intrinsic_value_per_share")
            features["dcf_enterprise_value"] = dcf_prediction.get("enterprise_value")
        return features