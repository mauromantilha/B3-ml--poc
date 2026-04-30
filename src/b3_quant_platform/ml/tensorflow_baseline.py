from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import select
from sqlalchemy.orm import Session

from b3_quant_platform.core.config import Settings, get_settings
from b3_quant_platform.models.entities import ModelRegistry, ModelRun, PortfolioInstance, TrainingRun
from b3_quant_platform.models.enums import RunStatus
from b3_quant_platform.schemas.jobs import TrainModelRequest


class TensorflowBaselineService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def train(self, session: Session, payload: TrainModelRequest) -> tuple[ModelRun, dict[str, Any]]:
        if not payload.rows:
            raise ValueError("Training rows are required")

        feature_names = sorted(payload.rows[0].features.keys())
        features = [self._row_to_vector(row.features, feature_names) for row in payload.rows]
        targets = [float(row.target) for row in payload.rows]
        dataset_fingerprint = self._dataset_fingerprint(payload)
        portfolio = session.get(PortfolioInstance, payload.portfolio_id)
        strategy_id = portfolio.template_id if portfolio is not None else None

        tf = importlib.import_module("tensorflow")
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(len(feature_names),)),
                tf.keras.layers.Dense(16, activation="relu"),
                tf.keras.layers.Dense(8, activation="relu"),
                tf.keras.layers.Dense(1),
            ]
        )
        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        history = model.fit(features, targets, epochs=payload.epochs, verbose=0)
        predictions = model.predict(features, verbose=0).flatten().tolist()

        artifact_path = self._artifact_path(payload.model_name, payload.version, payload.reference_date.isoformat())
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(artifact_path))

        registry = session.scalar(
            select(ModelRegistry).where(
                ModelRegistry.model_name == payload.model_name,
                ModelRegistry.version == payload.version,
            )
        )
        metrics = {
            "loss": float(history.history["loss"][-1]),
            "mae": float(history.history["mae"][-1]),
            "feature_names": feature_names,
        }
        if registry is None:
            registry = ModelRegistry(
                strategy_id=strategy_id,
                model_name=payload.model_name,
                version=payload.version,
                objective=payload.objective,
                artifact_uri=str(artifact_path),
                metrics_json=metrics,
                active=True,
            )
            session.add(registry)
            session.flush()
        else:
            if strategy_id is not None:
                registry.strategy_id = strategy_id
            registry.objective = payload.objective
            registry.artifact_uri = str(artifact_path)
            registry.metrics_json = metrics

        training_run = session.scalar(
            select(TrainingRun).where(
                TrainingRun.model_id == registry.id,
                TrainingRun.reference_date == payload.reference_date,
                TrainingRun.dataset_fingerprint == dataset_fingerprint,
            )
        )
        parameters = {"epochs": payload.epochs, "row_count": len(payload.rows)}
        if training_run is None:
            training_run = TrainingRun(
                model_id=registry.id,
                strategy_id=strategy_id,
                reference_date=payload.reference_date,
                dataset_fingerprint=dataset_fingerprint,
                feature_set_version="v1",
                status=RunStatus.SUCCEEDED,
                parameters_json=parameters,
                metrics_json=metrics,
                artifact_uri=str(artifact_path),
            )
            session.add(training_run)
            session.flush()
        else:
            training_run.strategy_id = strategy_id
            training_run.status = RunStatus.SUCCEEDED
            training_run.parameters_json = parameters
            training_run.metrics_json = metrics
            training_run.artifact_uri = str(artifact_path)

        model_run = session.scalar(
            select(ModelRun).where(
                ModelRun.model_id == registry.id,
                ModelRun.portfolio_id == payload.portfolio_id,
                ModelRun.reference_date == payload.reference_date,
                ModelRun.horizon_days == 1,
            )
        )
        prediction_payload = {
            "feature_names": feature_names,
            "sample_predictions": [float(value) for value in predictions[:10]],
        }
        if model_run is None:
            model_run = ModelRun(
                model_id=registry.id,
                training_run_id=training_run.id,
                portfolio_id=payload.portfolio_id,
                reference_date=payload.reference_date,
                horizon_days=1,
                status=RunStatus.SUCCEEDED,
                metrics_json=metrics,
                predictions_json=prediction_payload,
            )
            session.add(model_run)
        else:
            model_run.training_run_id = training_run.id
            model_run.status = RunStatus.SUCCEEDED
            model_run.metrics_json = metrics
            model_run.predictions_json = prediction_payload

        session.flush()
        session.refresh(model_run)
        return model_run, {
            "artifact_uri": str(artifact_path),
            "loss": metrics["loss"],
            "mae": metrics["mae"],
            "feature_names": feature_names,
            "sample_predictions": prediction_payload["sample_predictions"],
        }

    def _artifact_path(self, model_name: str, version: str, date_slug: str) -> Path:
        return self.settings.tf_artifact_dir / model_name / version / date_slug / "model.keras"

    @staticmethod
    def _row_to_vector(features: dict[str, float], feature_names: list[str]) -> list[float]:
        if sorted(features.keys()) != feature_names:
            raise ValueError("All training rows must provide the same feature names")
        return [float(features[name]) for name in feature_names]

    @staticmethod
    def _dataset_fingerprint(payload: TrainModelRequest) -> str:
        rows_payload = payload.model_dump(mode="json")["rows"]
        return hashlib.sha256(orjson.dumps(rows_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
