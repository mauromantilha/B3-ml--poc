from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from b3_quant_platform.ingestion.models import HistoricalDatasetType
from b3_quant_platform.schemas.common import JobRunEnvelope


class AnalyticsMaterializationStrategy(StrEnum):
    AUTO = "auto"
    EXTERNAL_ONLY = "external_only"
    EXTERNAL_AND_NATIVE = "external_and_native"
    NATIVE_ONLY = "native_only"


class ExpectedCloseInput(BaseModel):
    ticker: str
    expected_close: Decimal = Field(..., ge=0)


class EodReconcileRequest(BaseModel):
    reference_date: date
    portfolio_id: UUID
    scenario_slug: str = "baseline"
    expected_prices: list[ExpectedCloseInput]


class AnalyticsMirrorRequest(BaseModel):
    reference_date: date | None = None
    processing_date: date = Field(default_factory=date.today)
    market: str = "equities"
    ticker: str = "MULTI"
    table_name: str = "eod_comparisons"
    dataset_name: str = "quotes"
    source_prefix: str | None = None
    target_prefix: str = "curated"
    rows: list[dict[str, Any]] = Field(default_factory=list)
    materialization_strategy: AnalyticsMaterializationStrategy = AnalyticsMaterializationStrategy.AUTO
    required_columns: list[str] = Field(default_factory=list)
    partition_field: str = "reference_date"
    cluster_fields: list[str] = Field(default_factory=list)
    external_dataset: str | None = None
    native_dataset: str | None = None
    limit_files: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_source_mode(self) -> "AnalyticsMirrorRequest":
        if not self.rows and not self.source_prefix:
            self.source_prefix = f"b3/silver/{self.dataset_name.strip('/')}/"
        return self


class HistoricalIngestionRequest(BaseModel):
    dataset_type: HistoricalDatasetType
    processing_date: date = Field(default_factory=date.today)
    reference_date: date | None = None
    source_system: str = "b3"
    file_path: str | None = None
    source_name: str | None = None
    content_base64: str | None = None
    encoding: str = "latin-1"
    delimiter: str | None = None

    @model_validator(mode="after")
    def validate_input_source(self) -> "HistoricalIngestionRequest":
        if not self.file_path and not self.content_base64:
            raise ValueError("Either file_path or content_base64 must be provided")
        if self.content_base64 and not self.source_name:
            raise ValueError("source_name is required when content_base64 is provided")
        return self


class TrainingRow(BaseModel):
    features: dict[str, float]
    target: float


class TrainModelRequest(BaseModel):
    reference_date: date
    portfolio_id: UUID
    model_name: str
    version: str
    objective: str
    epochs: int = Field(default=15, ge=1, le=500)
    rows: list[TrainingRow]


class JobResult(BaseModel):
    job_run: JobRunEnvelope
    details: dict[str, Any]
