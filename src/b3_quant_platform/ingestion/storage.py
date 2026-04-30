from __future__ import annotations

import io
import json
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
class StoredObject:
    key: str
    storage_uri: str
    local_path: Path


class R2ObjectStorageClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return all(
            [
                self.settings.r2_endpoint_url,
                self.settings.r2_access_key_id,
                self.settings.r2_secret_access_key,
                self.settings.r2_bucket,
            ]
        )

    def object_uri(self, key: str) -> str:
        return f"r2://{self.settings.r2_bucket}/{key}"

    @default_retry()
    def put_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("R2 client is not configured")
        client = self._get_client()
        client.put_object(
            Bucket=self.settings.r2_bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
            Metadata=metadata or {},
        )
        return self.object_uri(key)

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.r2_endpoint_url,
                aws_access_key_id=self.settings.r2_access_key_id,
                aws_secret_access_key=self.settings.r2_secret_access_key,
                region_name=self.settings.r2_region,
            )
        return self._client


class HistoricalLakeWriter:
    def __init__(
        self,
        settings: Settings | None = None,
        storage_client: R2ObjectStorageClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage_client = storage_client or R2ObjectStorageClient(self.settings)

    def write_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        local_path = self.settings.local_parquet_dir / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(payload)

        storage_uri = str(local_path)
        if self.storage_client.enabled:
            storage_uri = self.storage_client.put_bytes(
                key,
                payload,
                content_type=content_type,
                metadata=metadata,
            )

        logger.info("historical_object_written", key=key, storage_uri=storage_uri)
        return StoredObject(key=key, storage_uri=storage_uri, local_path=local_path)

    def write_json(self, key: str, payload: dict[str, Any]) -> StoredObject:
        data = json.dumps(self._normalise_value(payload), ensure_ascii=True, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        return self.write_bytes(key, data, content_type="application/json")

    def write_parquet(self, key: str, records: list[dict[str, Any]]) -> StoredObject:
        table = pa.Table.from_pylist([self._normalise_record(record) for record in records])
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        return self.write_bytes(key, buffer.getvalue())

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