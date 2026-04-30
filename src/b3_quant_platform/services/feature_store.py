from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from b3_quant_platform.models.entities import FeatureStoreSnapshot
from b3_quant_platform.models.enums import EconomicModelWindow
from b3_quant_platform.repositories.economic_models import FeatureStoreSnapshotRepository


class FeatureStoreService:
    def upsert_economic_features(
        self,
        session: Session,
        *,
        portfolio_id: UUID | None,
        entity_key: str,
        reference_date: date,
        window: EconomicModelWindow,
        features_json: dict[str, Any],
        source_models: list[str],
    ) -> FeatureStoreSnapshot:
        return FeatureStoreSnapshotRepository(session).upsert_snapshot(
            portfolio_id=portfolio_id,
            entity_key=entity_key,
            feature_namespace="economic_models_engine",
            reference_date=reference_date,
            window=window,
            source_models_json=source_models,
            features_json=features_json,
        )