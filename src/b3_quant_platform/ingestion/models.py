from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any


class HistoricalDatasetType(StrEnum):
    COTAHIST = "cotahist"
    EOD = "eod"


def serialise_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: serialise_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialise_value(item) for item in value]
    return value


@dataclass(slots=True, frozen=True)
class SourceFileDescriptor:
    path: Path
    dataset_type: HistoricalDatasetType
    processing_date: date
    source_system: str = "b3"
    reference_date: date | None = None
    encoding: str = "latin-1"
    delimiter: str | None = None


@dataclass(slots=True)
class ParsedHistoricalRecord:
    reference_date: date
    bdi_code: str
    ticker: str
    market_type_code: int
    instrument_name: str
    specification_code: str
    term_days: str | None
    currency: str
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    average_price: Decimal
    close_price: Decimal
    best_bid_price: Decimal
    best_ask_price: Decimal
    trade_count: int
    trade_quantity: int
    trade_volume: Decimal
    exercise_price: Decimal | None
    option_indicator: str | None
    expiration_date: date | None
    price_factor: int
    strike_points: Decimal | None
    isin: str | None
    distribution_number: int | None
    source_line_number: int

    def to_dict(self) -> dict[str, Any]:
        return serialise_value(asdict(self))


@dataclass(slots=True)
class ParsedHistoricalFile:
    dataset_type: HistoricalDatasetType
    source_name: str
    source_system: str
    source_checksum: str
    processing_date: date
    reference_date: date | None
    records: list[ParsedHistoricalRecord]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialise_value(
            {
                "dataset_type": self.dataset_type.value,
                "source_name": self.source_name,
                "source_system": self.source_system,
                "source_checksum": self.source_checksum,
                "processing_date": self.processing_date,
                "reference_date": self.reference_date,
                "records": [record.to_dict() for record in self.records],
                "metadata": self.metadata,
            }
        )


@dataclass(slots=True)
class ValidationIssue:
    line_number: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"line_number": self.line_number, "code": self.code, "message": self.message}


@dataclass(slots=True)
class HistoricalIngestionManifest:
    ingestion_id: str
    dataset_type: str
    source_file_name: str
    source_system: str
    source_checksum: str
    processing_date: date
    reference_date: date | None
    source_record_count: int
    deduplicated_record_count: int
    duplicate_count: int
    instrument_count: int
    bronze_raw_uri: str
    bronze_metadata_uri: str
    silver_quotes_uris: list[str]
    silver_instruments_uri: str
    metadata_log_uri: str
    started_at: datetime
    completed_at: datetime
    deduplication_rule: str
    partitions: list[dict[str, Any]]
    validation_issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialise_value(asdict(self))


@dataclass(slots=True)
class HistoricalIngestionResult:
    manifest: HistoricalIngestionManifest
    bronze_local_path: Path
    silver_quote_local_paths: list[Path]
    silver_instruments_local_path: Path
