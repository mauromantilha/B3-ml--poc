from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from b3_quant_platform.models.entities import EodComparison, ModelRegistry, PredictionRun, TrainingRun
from b3_quant_platform.models.enums import ComparisonVerdict, RunStatus
from b3_quant_platform.repositories.base import SQLAlchemyRepository


class ModelRegistryRepository(SQLAlchemyRepository[ModelRegistry]):
    model = ModelRegistry

    def upsert_model(
        self,
        *,
        model_name: str,
        version: str,
        objective: str,
        artifact_uri: str,
        framework: str = "tensorflow",
        strategy_id: UUID | None = None,
        metrics_json: dict[str, Any] | None = None,
    ) -> ModelRegistry:
        model = self.session.scalar(
            select(ModelRegistry).where(
                ModelRegistry.model_name == model_name,
                ModelRegistry.version == version,
            )
        )
        if model is None:
            model = ModelRegistry(
                strategy_id=strategy_id,
                model_name=model_name,
                version=version,
                framework=framework,
                objective=objective,
                artifact_uri=artifact_uri,
                metrics_json=metrics_json or {},
                tags_json=[],
                active=True,
            )
            return self.add(model)

        model.strategy_id = strategy_id
        model.objective = objective
        model.framework = framework
        model.artifact_uri = artifact_uri
        model.metrics_json = metrics_json or {}
        self.session.flush()
        return model


class TrainingRunRepository(SQLAlchemyRepository[TrainingRun]):
    model = TrainingRun

    def create_training_run(
        self,
        *,
        model_id: UUID,
        reference_date: date,
        dataset_fingerprint: str,
        artifact_uri: str,
        status: RunStatus,
        strategy_id: UUID | None = None,
        parameters_json: dict[str, Any] | None = None,
        metrics_json: dict[str, Any] | None = None,
    ) -> TrainingRun:
        run = TrainingRun(
            model_id=model_id,
            strategy_id=strategy_id,
            reference_date=reference_date,
            dataset_fingerprint=dataset_fingerprint,
            artifact_uri=artifact_uri,
            status=status,
            feature_set_version="v1",
            parameters_json=parameters_json or {},
            metrics_json=metrics_json or {},
        )
        return self.add(run)


class PredictionRunRepository(SQLAlchemyRepository[PredictionRun]):
    model = PredictionRun

    def upsert_prediction_run(
        self,
        *,
        model_id: UUID,
        portfolio_id: UUID,
        reference_date: date,
        horizon_days: int,
        status: RunStatus,
        training_run_id: UUID | None = None,
        metrics_json: dict[str, Any] | None = None,
        predictions_json: dict[str, Any] | None = None,
    ) -> PredictionRun:
        run = self.session.scalar(
            select(PredictionRun).where(
                PredictionRun.model_id == model_id,
                PredictionRun.portfolio_id == portfolio_id,
                PredictionRun.reference_date == reference_date,
                PredictionRun.horizon_days == horizon_days,
            )
        )
        if run is None:
            run = PredictionRun(
                model_id=model_id,
                training_run_id=training_run_id,
                portfolio_id=portfolio_id,
                reference_date=reference_date,
                horizon_days=horizon_days,
                status=status,
                metrics_json=metrics_json or {},
                predictions_json=predictions_json or {},
            )
            return self.add(run)

        run.training_run_id = training_run_id
        run.status = status
        run.metrics_json = metrics_json or {}
        run.predictions_json = predictions_json or {}
        self.session.flush()
        return run


class EodComparisonRepository(SQLAlchemyRepository[EodComparison]):
    model = EodComparison

    def upsert_comparison(
        self,
        *,
        portfolio_id: UUID,
        reference_date: date,
        ticker: str,
        scenario_slug: str,
        expected_close: Decimal,
        actual_close: Decimal,
        tracking_error_bps: Decimal,
        verdict: ComparisonVerdict,
        prediction_run_id: UUID | None = None,
        comparison_details_json: dict[str, Any] | None = None,
    ) -> EodComparison:
        comparison = self.session.scalar(
            select(EodComparison).where(
                EodComparison.portfolio_id == portfolio_id,
                EodComparison.reference_date == reference_date,
                EodComparison.ticker == ticker,
                EodComparison.scenario_slug == scenario_slug,
            )
        )
        if comparison is None:
            comparison = EodComparison(
                portfolio_id=portfolio_id,
                prediction_run_id=prediction_run_id,
                reference_date=reference_date,
                ticker=ticker,
                scenario_slug=scenario_slug,
                expected_close=expected_close,
                actual_close=actual_close,
                tracking_error_bps=tracking_error_bps,
                verdict=verdict,
                comparison_details_json=comparison_details_json or {},
            )
            return self.add(comparison)

        comparison.prediction_run_id = prediction_run_id
        comparison.expected_close = expected_close
        comparison.actual_close = actual_close
        comparison.tracking_error_bps = tracking_error_bps
        comparison.verdict = verdict
        comparison.comparison_details_json = comparison_details_json or {}
        self.session.flush()
        return comparison
