from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from b3_quant_platform.core.config import Settings, get_settings
from b3_quant_platform.core.logging import get_logger
from b3_quant_platform.core.retry import default_retry

logger = get_logger(__name__)


@dataclass(slots=True)
class LakeWriteResult:
    storage_uri: str
    local_path: Path
    row_count: int


class LakeWriterService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_partition_key(
        self,
        *,
        layer: str,
        reference_date: date,
        market: str,
        ticker: str,
        artifact_name: str,
    ) -> str:
        return (
            f"{layer}/date={reference_date.isoformat()}/market={market}/"
            f"ticker={ticker}/{artifact_name}.parquet"
        )

    def write_records(
        self,
        records: list[dict[str, Any]],
        *,
        layer: str,
        reference_date: date,
        market: str,
        ticker: str,
        artifact_name: str,
    ) -> LakeWriteResult:
        normalised_records = [self._normalise_record(record) for record in records]
        parquet_bytes = self._records_to_parquet(normalised_records)
        key = self.build_partition_key(
            layer=layer,
            reference_date=reference_date,
            market=market,
            ticker=ticker,
            artifact_name=artifact_name,
        )
        local_path = self.settings.local_parquet_dir / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(parquet_bytes)

        storage_uri = str(local_path)
        if self._r2_enabled:
            self._upload_to_r2(key, parquet_bytes)
            storage_uri = f"r2://{self.settings.r2_bucket}/{key}"

        logger.info(
            "lake_write_completed",
            layer=layer,
            market=market,
            ticker=ticker,
            row_count=len(normalised_records),
            storage_uri=storage_uri,
        )
        return LakeWriteResult(storage_uri=storage_uri, local_path=local_path, row_count=len(normalised_records))

    @property
    def _r2_enabled(self) -> bool:
        return all(
            [
                self.settings.r2_endpoint_url,
                self.settings.r2_access_key_id,
                self.settings.r2_secret_access_key,
                self.settings.r2_bucket,
            ]
        )

    @default_retry()
    def _upload_to_r2(self, key: str, payload: bytes) -> None:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name=self.settings.r2_region,
        )
        client.put_object(Bucket=self.settings.r2_bucket, Key=key, Body=payload)

    def _records_to_parquet(self, records: list[dict[str, Any]]) -> bytes:
        table = pa.Table.from_pylist(records)
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        return buffer.getvalue()

    def _normalise_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {key: self._normalise_value(value) for key, value in record.items()}

    def _normalise_value(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: self._normalise_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._normalise_value(item) for item in value]
        return value
