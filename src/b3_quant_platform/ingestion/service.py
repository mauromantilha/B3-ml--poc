from __future__ import annotations

import hashlib
import mimetypes
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from b3_quant_platform.core.config import Settings, get_settings
from b3_quant_platform.core.logging import get_logger
from b3_quant_platform.ingestion.deduplication import HistoricalDeduplicator
from b3_quant_platform.ingestion.enrichment import HistoricalRecordEnricher
from b3_quant_platform.ingestion.models import (
    HistoricalDatasetType,
    HistoricalIngestionManifest,
    HistoricalIngestionResult,
    ParsedHistoricalFile,
    SourceFileDescriptor,
)
from b3_quant_platform.ingestion.parsers import HistoricalB3Parser
from b3_quant_platform.ingestion.storage import HistoricalLakeWriter
from b3_quant_platform.ingestion.validators import HistoricalFileValidator

logger = get_logger(__name__)


class HistoricalB3IngestionService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        parser: HistoricalB3Parser | None = None,
        validator: HistoricalFileValidator | None = None,
        enricher: HistoricalRecordEnricher | None = None,
        deduplicator: HistoricalDeduplicator | None = None,
        writer: HistoricalLakeWriter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.parser = parser or HistoricalB3Parser()
        self.validator = validator or HistoricalFileValidator()
        self.enricher = enricher or HistoricalRecordEnricher()
        self.deduplicator = deduplicator or HistoricalDeduplicator()
        self.writer = writer or HistoricalLakeWriter(self.settings)

    def ingest_file(
        self,
        *,
        file_path: Path,
        dataset_type: HistoricalDatasetType | str,
        processing_date: date | None = None,
        reference_date: date | None = None,
        source_system: str = "b3",
        encoding: str = "latin-1",
        delimiter: str | None = None,
    ) -> HistoricalIngestionResult:
        resolved_dataset_type = HistoricalDatasetType(dataset_type)
        descriptor = SourceFileDescriptor(
            path=file_path,
            dataset_type=resolved_dataset_type,
            processing_date=processing_date or date.today(),
            source_system=source_system,
            reference_date=reference_date,
            encoding=encoding,
            delimiter=delimiter,
        )
        return self.ingest_bytes(file_path.read_bytes(), descriptor=descriptor)

    def ingest_bytes(self, payload: bytes, *, descriptor: SourceFileDescriptor) -> HistoricalIngestionResult:
        started_at = datetime.now(timezone.utc)
        source_checksum = hashlib.sha256(payload).hexdigest()
        ingestion_id = self._build_ingestion_id(descriptor, source_checksum)
        logger.info(
            "historical_ingestion_started",
            ingestion_id=ingestion_id,
            dataset_type=descriptor.dataset_type.value,
            file_name=descriptor.path.name,
            processing_date=descriptor.processing_date.isoformat(),
            source_checksum=source_checksum,
        )

        parsed_file = self.parser.parse(payload, descriptor=descriptor, source_checksum=source_checksum)
        validation_issues = self.validator.assert_valid(parsed_file)
        normalised_records = self._normalise_records(parsed_file)
        deduplicated_records, duplicate_count = self.deduplicator.deduplicate(normalised_records)
        instrument_rows = self.deduplicator.build_instrument_rows(deduplicated_records)

        bronze_raw_key = self._build_bronze_raw_key(parsed_file, source_checksum)
        bronze_metadata_key = self._build_bronze_metadata_key(parsed_file, ingestion_id)
        bronze_raw = self.writer.write_bytes(
            bronze_raw_key,
            payload,
            content_type=self._guess_content_type(descriptor.path),
            metadata={"sha256": source_checksum, "dataset_type": descriptor.dataset_type.value},
        )
        bronze_metadata = self.writer.write_json(
            bronze_metadata_key,
            {
                "ingestion_id": ingestion_id,
                "dataset_type": parsed_file.dataset_type.value,
                "source_file_name": parsed_file.source_name,
                "source_checksum": source_checksum,
                "processing_date": parsed_file.processing_date,
                "reference_date": parsed_file.reference_date,
                "raw_line_count": parsed_file.metadata.get("raw_line_count"),
                "source_record_count": len(parsed_file.records),
            },
        )

        quote_objects = []
        partitions = []
        for key, records in self._group_quote_records(deduplicated_records).items():
            market_type, year_value, month_value = key
            quote_key = (
                f"b3/silver/quotes/market_type={market_type}/year={year_value}/month={month_value:02d}/"
                f"quotes_{ingestion_id}.parquet"
            )
            stored = self.writer.write_parquet(quote_key, records)
            quote_objects.append(stored)
            partitions.append(
                {
                    "dataset": "quotes",
                    "market_type": market_type,
                    "year": year_value,
                    "month": month_value,
                    "storage_uri": stored.storage_uri,
                    "row_count": len(records),
                }
            )

        instruments_key = (
            f"b3/silver/instruments/year={descriptor.processing_date.year}/month={descriptor.processing_date.month:02d}/"
            f"instruments_{ingestion_id}.parquet"
        )
        instruments_object = self.writer.write_parquet(instruments_key, instrument_rows)
        metadata_log_key = (
            f"b3/metadata/ingestion_logs/date={descriptor.processing_date.isoformat()}/ingestion_{ingestion_id}.json"
        )
        metadata_log_uri = self._storage_uri_for_key(metadata_log_key)

        completed_at = datetime.now(timezone.utc)
        manifest = HistoricalIngestionManifest(
            ingestion_id=ingestion_id,
            dataset_type=descriptor.dataset_type.value,
            source_file_name=descriptor.path.name,
            source_system=descriptor.source_system,
            source_checksum=source_checksum,
            processing_date=descriptor.processing_date,
            reference_date=parsed_file.reference_date,
            source_record_count=len(parsed_file.records),
            deduplicated_record_count=len(deduplicated_records),
            duplicate_count=duplicate_count,
            instrument_count=len(instrument_rows),
            bronze_raw_uri=bronze_raw.storage_uri,
            bronze_metadata_uri=bronze_metadata.storage_uri,
            silver_quotes_uris=[item.storage_uri for item in quote_objects],
            silver_instruments_uri=instruments_object.storage_uri,
            metadata_log_uri=metadata_log_uri,
            started_at=started_at,
            completed_at=completed_at,
            deduplication_rule=self.deduplicator.deduplication_rule,
            partitions=partitions,
            validation_issues=[issue.to_dict() for issue in validation_issues],
        )
        self.writer.write_json(metadata_log_key, manifest.to_dict())

        logger.info(
            "historical_ingestion_completed",
            ingestion_id=ingestion_id,
            dataset_type=descriptor.dataset_type.value,
            source_records=len(parsed_file.records),
            deduplicated_records=len(deduplicated_records),
            quote_partitions=len(quote_objects),
            instruments=len(instrument_rows),
            metadata_log_uri=metadata_log_uri,
        )
        return HistoricalIngestionResult(
            manifest=manifest,
            bronze_local_path=bronze_raw.local_path,
            silver_quote_local_paths=[item.local_path for item in quote_objects],
            silver_instruments_local_path=instruments_object.local_path,
        )

    def _normalise_records(self, parsed_file: ParsedHistoricalFile) -> list[dict[str, Any]]:
        return [
            self.enricher.enrich(
                record,
                dataset_type=parsed_file.dataset_type.value,
                processing_date=parsed_file.processing_date,
                source_checksum=parsed_file.source_checksum,
                source_name=parsed_file.source_name,
            )
            for record in parsed_file.records
        ]

    def _build_ingestion_id(self, descriptor: SourceFileDescriptor, source_checksum: str) -> str:
        seed = (
            f"{descriptor.dataset_type.value}:{descriptor.processing_date.isoformat()}:"
            f"{descriptor.path.name}:{source_checksum}"
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]

    def _build_bronze_raw_key(self, parsed_file: ParsedHistoricalFile, source_checksum: str) -> str:
        checksum_prefix = source_checksum[:16]
        if parsed_file.dataset_type == HistoricalDatasetType.COTAHIST:
            year_value = parsed_file.reference_date.year if parsed_file.reference_date else parsed_file.processing_date.year
            return (
                f"b3/bronze/cotahist/year={year_value}/processing_date={parsed_file.processing_date.isoformat()}/"
                f"source_sha256={checksum_prefix}/{parsed_file.source_name}"
            )
        reference_value = parsed_file.reference_date or parsed_file.processing_date
        return (
            f"b3/bronze/eod/date={reference_value.isoformat()}/processing_date={parsed_file.processing_date.isoformat()}/"
            f"source_sha256={checksum_prefix}/{parsed_file.source_name}"
        )

    def _build_bronze_metadata_key(self, parsed_file: ParsedHistoricalFile, ingestion_id: str) -> str:
        if parsed_file.dataset_type == HistoricalDatasetType.COTAHIST:
            year_value = parsed_file.reference_date.year if parsed_file.reference_date else parsed_file.processing_date.year
            return (
                f"b3/bronze/cotahist/year={year_value}/processing_date={parsed_file.processing_date.isoformat()}/"
                f"ingestion_{ingestion_id}.json"
            )
        reference_value = parsed_file.reference_date or parsed_file.processing_date
        return (
            f"b3/bronze/eod/date={reference_value.isoformat()}/processing_date={parsed_file.processing_date.isoformat()}/"
            f"ingestion_{ingestion_id}.json"
        )

    def _group_quote_records(
        self, records: list[dict[str, Any]]
    ) -> dict[tuple[str, int, int], list[dict[str, Any]]]:
        grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            reference_date = record["reference_date"]
            grouped[(record["market_type"], reference_date.year, reference_date.month)].append(record)
        return grouped

    def _storage_uri_for_key(self, key: str) -> str:
        if self.writer.storage_client.enabled:
            return self.writer.storage_client.object_uri(key)
        return str(self.settings.local_parquet_dir / key)

    def _guess_content_type(self, path: Path) -> str:
        content_type, _ = mimetypes.guess_type(path.name)
        return content_type or "application/octet-stream"