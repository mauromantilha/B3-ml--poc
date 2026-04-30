from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from b3_quant_platform.core.config import Settings, get_settings
from b3_quant_platform.core.logging import get_logger
from b3_quant_platform.core.retry import default_retry
from b3_quant_platform.schemas.jobs import AnalyticsMaterializationStrategy, AnalyticsMirrorRequest

logger = get_logger(__name__)


DEFAULT_DATASET_POLICIES: dict[str, dict[str, Any]] = {
    "quotes": {
        "required_columns": ["reference_date", "ticker", "market_type", "close_price", "source_checksum"],
        "partition_field": "reference_date",
        "cluster_fields": ["market_type", "ticker"],
        "merge_keys": ["reference_date", "market_type", "ticker", "source_checksum"],
    },
    "instruments": {
        "required_columns": ["ticker", "asset_type", "segment", "source_checksum"],
        "partition_field": "last_processing_date",
        "cluster_fields": ["asset_type", "segment", "ticker"],
        "merge_keys": ["ticker", "isin", "source_checksum"],
    },
}


@dataclass(slots=True)
class AnalyticsSourceObject:
    key: str
    last_modified: datetime
    size: int
    etag: str | None = None


@dataclass(slots=True)
class MirroredAnalyticsObject:
    source_key: str
    source_checksum: str
    source_last_modified: str
    target_key: str
    target_uri: str
    target_checksum: str
    row_count: int
    schema_fields: list[str]
    zone: str = "external_raw_analytics"
    consistency_status: str = "matched"


@dataclass(slots=True)
class AnalyticsMirrorWatermark:
    dataset_name: str
    source_prefix: str
    last_processed_at: str | None
    last_processed_key: str | None
    last_manifest_uri: str | None
    last_checked_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalyticsMirrorResult:
    gcs_uri: str
    local_path: Path
    bigquery_table: str | None
    manifest_uri: str | None = None
    watermark_uri: str | None = None
    external_table: str | None = None
    native_table: str | None = None
    mirrored_object_count: int = 0
    mirrored_uris: list[str] = field(default_factory=list)
    consistency_checks: list[dict[str, Any]] = field(default_factory=list)
    ddl_statements: dict[str, str] = field(default_factory=dict)
    dml_statements: dict[str, str] = field(default_factory=dict)


class AnalyticsMirrorService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def mirror_rows(self, payload: AnalyticsMirrorRequest) -> AnalyticsMirrorResult:
        key = self._build_key(payload)
        local_path = self.settings.local_parquet_dir / "gcs_mirror" / key
        local_path.parent.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pylist([self._normalise_record(row) for row in payload.rows])
        pq.write_table(table, local_path, compression="snappy")

        gcs_uri = str(local_path)
        bigquery_table: str | None = None
        if self._gcs_enabled:
            self._upload_to_gcs(key, local_path.read_bytes())
            gcs_uri = f"gs://{self.settings.gcs_bucket}/{key}"
            if self.settings.bigquery_project_id:
                bigquery_table = self._register_biglake_table(payload.table_name, gcs_uri)

        logger.info(
            "analytics_mirror_completed",
            gcs_uri=gcs_uri,
            bigquery_table=bigquery_table,
            row_count=len(payload.rows),
        )
        return AnalyticsMirrorResult(gcs_uri=gcs_uri, local_path=local_path, bigquery_table=bigquery_table)

    def mirror_dataset(self, payload: AnalyticsMirrorRequest) -> AnalyticsMirrorResult:
        source_prefix = payload.source_prefix or f"b3/silver/{payload.dataset_name.strip('/')}/"
        watermark = self._read_watermark(payload.dataset_name)
        source_objects = self._list_source_objects(source_prefix)
        new_objects = self._filter_new_objects(source_objects, watermark, payload.limit_files)
        mirrored_objects: list[MirroredAnalyticsObject] = []
        shared_schema: pa.Schema | None = None

        for source_object in new_objects:
            source_bytes = self._read_source_bytes(source_object.key)
            validation = self._validate_source_payload(payload, source_bytes)
            shared_schema = validation["schema"]
            source_checksum = hashlib.sha256(source_bytes).hexdigest()
            target_key = self._build_target_object_key(payload, source_object.key)
            target_object = self._write_to_gcs(target_key, source_bytes)
            mirrored_objects.append(
                MirroredAnalyticsObject(
                    source_key=source_object.key,
                    source_checksum=source_checksum,
                    source_last_modified=source_object.last_modified.isoformat(),
                    target_key=target_key,
                    target_uri=target_object["uri"],
                    target_checksum=source_checksum,
                    row_count=validation["row_count"],
                    schema_fields=validation["schema"].names,
                )
            )

        external_table_ref, native_table_ref, ddl_statements, dml_statements = self._publish_bigquery_assets(
            payload,
            mirrored_objects,
            shared_schema,
        )
        manifest_uri, manifest_local_path = self._write_manifest(
            payload,
            source_prefix,
            mirrored_objects,
            watermark,
            external_table_ref,
            native_table_ref,
            ddl_statements,
            dml_statements,
        )
        watermark_uri = self._write_watermark(
            payload,
            source_prefix,
            mirrored_objects,
            manifest_uri,
        )

        gcs_uri = manifest_uri or self._build_curated_root_uri(payload)
        bigquery_table = native_table_ref or external_table_ref
        logger.info(
            "analytics_dataset_mirror_completed",
            dataset_name=payload.dataset_name,
            source_prefix=source_prefix,
            mirrored_object_count=len(mirrored_objects),
            manifest_uri=manifest_uri,
            external_table=external_table_ref,
            native_table=native_table_ref,
        )
        return AnalyticsMirrorResult(
            gcs_uri=gcs_uri,
            local_path=manifest_local_path,
            bigquery_table=bigquery_table,
            manifest_uri=manifest_uri,
            watermark_uri=watermark_uri,
            external_table=external_table_ref,
            native_table=native_table_ref,
            mirrored_object_count=len(mirrored_objects),
            mirrored_uris=[item.target_uri for item in mirrored_objects],
            consistency_checks=[
                {
                    "source_key": item.source_key,
                    "target_uri": item.target_uri,
                    "source_checksum": item.source_checksum,
                    "target_checksum": item.target_checksum,
                    "status": item.consistency_status,
                }
                for item in mirrored_objects
            ],
            ddl_statements=ddl_statements,
            dml_statements=dml_statements,
        )

    def _build_key(self, payload: AnalyticsMirrorRequest) -> str:
        safe_table = re.sub(r"[^a-z0-9_]+", "_", payload.table_name.lower()).strip("_")
        reference_date = payload.reference_date or payload.processing_date
        return (
            f"curated/date={reference_date.isoformat()}/market={payload.market}/"
            f"ticker={payload.ticker}/{safe_table}.parquet"
        )

    def _build_target_object_key(self, payload: AnalyticsMirrorRequest, source_key: str) -> str:
        silver_root = "b3/silver/"
        relative_key = source_key[len(silver_root) :] if source_key.startswith(silver_root) else source_key
        return f"{payload.target_prefix.strip('/')}/external_raw_analytics/{relative_key}"

    def _build_curated_root_uri(self, payload: AnalyticsMirrorRequest) -> str:
        key = f"{payload.target_prefix.strip('/')}/external_raw_analytics/{payload.dataset_name.strip('/')}/"
        if self._gcs_enabled:
            return f"gs://{self.settings.gcs_bucket}/{key}"
        return str(self.settings.local_parquet_dir / "gcs_mirror" / key)

    def _filter_new_objects(
        self,
        source_objects: list[AnalyticsSourceObject],
        watermark: AnalyticsMirrorWatermark | None,
        limit_files: int | None,
    ) -> list[AnalyticsSourceObject]:
        if watermark is None or watermark.last_processed_at is None:
            filtered = source_objects
        else:
            last_processed_at = datetime.fromisoformat(watermark.last_processed_at)
            filtered = [
                item
                for item in source_objects
                if (item.last_modified, item.key)
                > (last_processed_at, watermark.last_processed_key or "")
            ]
        if limit_files is not None:
            return filtered[:limit_files]
        return filtered

    def _list_source_objects(self, prefix: str) -> list[AnalyticsSourceObject]:
        if self._r2_enabled:
            return self._list_r2_objects(prefix)
        return self._list_local_source_objects(prefix)

    def _list_local_source_objects(self, prefix: str) -> list[AnalyticsSourceObject]:
        root = self.settings.local_parquet_dir / prefix
        if not root.exists():
            return []
        objects: list[AnalyticsSourceObject] = []
        for file_path in sorted(root.rglob("*.parquet")):
            stat_result = file_path.stat()
            objects.append(
                AnalyticsSourceObject(
                    key=file_path.relative_to(self.settings.local_parquet_dir).as_posix(),
                    last_modified=datetime.fromtimestamp(stat_result.st_mtime, tz=UTC),
                    size=stat_result.st_size,
                    etag=None,
                )
            )
        return objects

    def _list_r2_objects(self, prefix: str) -> list[AnalyticsSourceObject]:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name=self.settings.r2_region,
        )
        continuation_token: str | None = None
        objects: list[AnalyticsSourceObject] = []
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.settings.r2_bucket, "Prefix": prefix}
            if continuation_token is not None:
                kwargs["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                key = item["Key"]
                if not key.endswith(".parquet"):
                    continue
                objects.append(
                    AnalyticsSourceObject(
                        key=key,
                        last_modified=item["LastModified"],
                        size=item["Size"],
                        etag=(item.get("ETag") or "").strip('"') or None,
                    )
                )
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        return sorted(objects, key=lambda item: (item.last_modified, item.key))

    def _read_source_bytes(self, key: str) -> bytes:
        if self._r2_enabled:
            return self._read_r2_object(key)
        return (self.settings.local_parquet_dir / key).read_bytes()

    def _read_r2_object(self, key: str) -> bytes:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name=self.settings.r2_region,
        )
        response = client.get_object(Bucket=self.settings.r2_bucket, Key=key)
        return response["Body"].read()

    def _validate_source_payload(self, payload: AnalyticsMirrorRequest, source_bytes: bytes) -> dict[str, Any]:
        table = pq.read_table(io.BytesIO(source_bytes))
        if table.num_rows == 0:
            raise ValueError("Analytics mirror does not accept empty parquet files")
        field_names = table.schema.names
        required_columns = payload.required_columns or self._dataset_policy(payload.dataset_name)["required_columns"]
        missing_columns = [column for column in required_columns if column not in field_names]
        if missing_columns:
            raise ValueError(f"Missing required columns for analytics mirror: {missing_columns}")
        return {"row_count": table.num_rows, "schema": table.schema}

    def _dataset_policy(self, dataset_name: str) -> dict[str, Any]:
        policy = DEFAULT_DATASET_POLICIES.get(dataset_name, DEFAULT_DATASET_POLICIES["quotes"])
        return dict(policy)

    def _write_to_gcs(self, key: str, payload: bytes) -> dict[str, Any]:
        local_path = self.settings.local_parquet_dir / "gcs_mirror" / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(payload)
        uri = str(local_path)
        if self._gcs_enabled:
            self._upload_to_gcs(key, payload)
            uri = f"gs://{self.settings.gcs_bucket}/{key}"
        return {"uri": uri, "local_path": local_path}

    def _write_manifest(
        self,
        payload: AnalyticsMirrorRequest,
        source_prefix: str,
        mirrored_objects: list[MirroredAnalyticsObject],
        previous_watermark: AnalyticsMirrorWatermark | None,
        external_table_ref: str | None,
        native_table_ref: str | None,
        ddl_statements: dict[str, str],
        dml_statements: dict[str, str],
    ) -> tuple[str, Path]:
        processing_date = payload.processing_date.isoformat()
        manifest_id = hashlib.sha256(
            f"{payload.dataset_name}:{processing_date}:{source_prefix}:{len(mirrored_objects)}".encode("utf-8")
        ).hexdigest()[:20]
        manifest_key = (
            f"{payload.target_prefix.strip('/')}/_control/manifests/dataset={payload.dataset_name}/"
            f"processing_date={processing_date}/mirror_{manifest_id}.json"
        )
        lineage = [asdict(item) for item in mirrored_objects]
        manifest_payload = {
            "manifest_id": manifest_id,
            "dataset_name": payload.dataset_name,
            "processing_date": processing_date,
            "source_prefix": source_prefix,
            "materialization_strategy": payload.materialization_strategy.value,
            "external_table": external_table_ref,
            "native_table": native_table_ref,
            "mirrored_object_count": len(mirrored_objects),
            "mirrored_uris": [item.target_uri for item in mirrored_objects],
            "lineage": lineage,
            "previous_watermark": previous_watermark.to_dict() if previous_watermark else None,
            "ddl_statements": ddl_statements,
            "dml_statements": dml_statements,
        }
        stored = self._write_json_to_gcs(manifest_key, manifest_payload)
        return stored["uri"], stored["local_path"]

    def _write_watermark(
        self,
        payload: AnalyticsMirrorRequest,
        source_prefix: str,
        mirrored_objects: list[MirroredAnalyticsObject],
        manifest_uri: str,
    ) -> str:
        latest = mirrored_objects[-1] if mirrored_objects else None
        watermark = AnalyticsMirrorWatermark(
            dataset_name=payload.dataset_name,
            source_prefix=source_prefix,
            last_processed_at=latest.source_last_modified if latest else None,
            last_processed_key=latest.source_key if latest else None,
            last_manifest_uri=manifest_uri,
            last_checked_at=datetime.now(tz=UTC).isoformat(),
        )
        local_path = self.settings.analytics_state_dir / f"analytics_mirror_{payload.dataset_name}.json"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(self._json_dumps(watermark.to_dict()))
        watermark_key = f"{payload.target_prefix.strip('/')}/_control/watermarks/{payload.dataset_name}.json"
        stored = self._write_json_to_gcs(watermark_key, watermark.to_dict())
        return stored["uri"]

    def _read_watermark(self, dataset_name: str) -> AnalyticsMirrorWatermark | None:
        path = self.settings.analytics_state_dir / f"analytics_mirror_{dataset_name}.json"
        if not path.exists():
            return None
        import json

        payload = json.loads(path.read_text())
        return AnalyticsMirrorWatermark(**payload)

    def _publish_bigquery_assets(
        self,
        payload: AnalyticsMirrorRequest,
        mirrored_objects: list[MirroredAnalyticsObject],
        shared_schema: pa.Schema | None,
    ) -> tuple[str | None, str | None, dict[str, str], dict[str, str]]:
        if shared_schema is None:
            return None, None, {}, {}
        statements = self._build_bigquery_statements(payload, mirrored_objects, shared_schema)
        if self._bigquery_enabled:
            if statements["external_table_sql"]:
                self._execute_bigquery_statement(statements["external_table_sql"])
            if statements["native_table_sql"]:
                self._execute_bigquery_statement(statements["native_table_sql"])
            if statements["native_merge_sql"]:
                self._execute_bigquery_statement(statements["native_merge_sql"])
        external_table = statements["external_table_ref"]
        native_table = statements["native_table_ref"]
        return (
            external_table,
            native_table,
            {"external_table_sql": statements["external_table_sql"], "native_table_sql": statements["native_table_sql"]},
            {"native_merge_sql": statements["native_merge_sql"]},
        )

    def _build_bigquery_statements(
        self,
        payload: AnalyticsMirrorRequest,
        mirrored_objects: list[MirroredAnalyticsObject],
        schema: pa.Schema,
    ) -> dict[str, str | None]:
        project_id = self.settings.bigquery_project_id or "<project-id>"
        external_dataset = payload.external_dataset or self.settings.bigquery_external_dataset or self.settings.bigquery_dataset
        native_dataset = payload.native_dataset or self.settings.bigquery_native_dataset or self.settings.bigquery_dataset
        safe_table = re.sub(r"[^a-z0-9_]+", "_", payload.table_name.lower()).strip("_")
        external_table_ref = f"{project_id}.{external_dataset}.{safe_table}_ext"
        native_table_ref = f"{project_id}.{native_dataset}.{safe_table}"
        base_uri = f"gs://{self.settings.gcs_bucket}/{payload.target_prefix.strip('/')}/external_raw_analytics/{payload.dataset_name.strip('/')}/"
        connection_clause = ""
        if self.settings.biglake_connection_id:
            connection_clause = f" WITH CONNECTION `{self.settings.biglake_connection_id}`"
        external_sql = (
            f"CREATE OR REPLACE EXTERNAL TABLE `{external_table_ref}`{connection_clause}\n"
            f"OPTIONS (\n"
            f"  format = 'PARQUET',\n"
            f"  uris = ['{base_uri}*'],\n"
            f"  hive_partition_uri_prefix = '{base_uri}',\n"
            f"  require_hive_partition_filter = FALSE\n"
            f");"
        )

        strategy = payload.materialization_strategy
        if strategy == AnalyticsMaterializationStrategy.EXTERNAL_ONLY:
            return {
                "external_table_ref": external_table_ref,
                "native_table_ref": None,
                "external_table_sql": external_sql,
                "native_table_sql": None,
                "native_merge_sql": None,
            }

        policy = self._dataset_policy(payload.dataset_name)
        partition_field = payload.partition_field or policy["partition_field"]
        cluster_fields = payload.cluster_fields or policy["cluster_fields"]
        schema_columns = self._build_native_table_schema(schema)
        schema_columns.append("lineage_source_uri STRING")
        schema_columns.append("mirrored_at TIMESTAMP")
        cluster_clause = f"\nCLUSTER BY {', '.join(cluster_fields)}" if cluster_fields else ""
        native_table_sql = (
            f"CREATE TABLE IF NOT EXISTS `{native_table_ref}` (\n  "
            + ",\n  ".join(schema_columns)
            + f"\n)\nPARTITION BY DATE({partition_field}){cluster_clause};"
        )
        source_uris = ", ".join(f"'{item.target_uri}'" for item in mirrored_objects)
        select_columns = ", ".join(f"`{field.name}`" for field in schema)
        merge_keys = policy["merge_keys"]
        on_clause = " AND ".join(f"T.`{field}` = S.`{field}`" for field in merge_keys if field in schema.names)
        if not on_clause:
            on_clause = "FALSE"
        update_set = ", ".join(f"`{field.name}` = S.`{field.name}`" for field in schema)
        insert_columns = ", ".join([f"`{field.name}`" for field in schema] + ["lineage_source_uri", "mirrored_at"])
        insert_values = ", ".join([f"S.`{field.name}`" for field in schema] + ["S.lineage_source_uri", "S.mirrored_at"])
        native_merge_sql = (
            f"MERGE `{native_table_ref}` T\n"
            f"USING (\n"
            f"  SELECT {select_columns}, _FILE_NAME AS lineage_source_uri, CURRENT_TIMESTAMP() AS mirrored_at\n"
            f"  FROM `{external_table_ref}`\n"
            f"  WHERE _FILE_NAME IN ({source_uris})\n"
            f") S\n"
            f"ON {on_clause}\n"
            f"WHEN MATCHED THEN UPDATE SET {update_set}, lineage_source_uri = S.lineage_source_uri, mirrored_at = S.mirrored_at\n"
            f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values});"
        )

        if strategy == AnalyticsMaterializationStrategy.AUTO and payload.dataset_name != "quotes":
            native_table_ref = None
            native_table_sql = None
            native_merge_sql = None

        return {
            "external_table_ref": external_table_ref,
            "native_table_ref": native_table_ref,
            "external_table_sql": external_sql,
            "native_table_sql": native_table_sql,
            "native_merge_sql": native_merge_sql,
        }

    def _build_native_table_schema(self, schema: pa.Schema) -> list[str]:
        return [f"`{field.name}` {self._map_pyarrow_type_to_bigquery(field.type)}" for field in schema]

    def _map_pyarrow_type_to_bigquery(self, arrow_type: pa.DataType) -> str:
        if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
            return "STRING"
        if pa.types.is_date32(arrow_type) or pa.types.is_date64(arrow_type):
            return "DATE"
        if pa.types.is_timestamp(arrow_type):
            return "TIMESTAMP"
        if pa.types.is_boolean(arrow_type):
            return "BOOL"
        if pa.types.is_integer(arrow_type):
            return "INT64"
        if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
            return "NUMERIC"
        if pa.types.is_list(arrow_type):
            value_type = self._map_pyarrow_type_to_bigquery(arrow_type.value_type)
            return f"ARRAY<{value_type}>"
        if pa.types.is_struct(arrow_type):
            fields = ", ".join(
                f"{field.name} {self._map_pyarrow_type_to_bigquery(field.type)}" for field in arrow_type
            )
            return f"STRUCT<{fields}>"
        return "STRING"

    @property
    def _r2_enabled(self) -> bool:
        return bool(
            self.settings.r2_endpoint_url
            and self.settings.r2_access_key_id
            and self.settings.r2_secret_access_key
            and self.settings.r2_bucket
        )

    @property
    def _gcs_enabled(self) -> bool:
        running_in_gcp = bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"))
        has_key_file = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        return bool(self.settings.gcs_bucket and (running_in_gcp or has_key_file))

    @property
    def _bigquery_enabled(self) -> bool:
        running_in_gcp = bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"))
        has_key_file = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        return bool(self.settings.bigquery_project_id and (running_in_gcp or has_key_file))

    @default_retry()
    def _upload_to_gcs(self, key: str, payload: bytes) -> None:
        from google.cloud import storage

        client = storage.Client(project=self.settings.bigquery_project_id or None)
        bucket = client.bucket(self.settings.gcs_bucket)
        blob = bucket.blob(key)
        blob.upload_from_string(payload, content_type="application/octet-stream")

    @default_retry()
    def _register_biglake_table(self, table_name: str, gcs_uri: str) -> str:
        from google.cloud import bigquery

        safe_table = re.sub(r"[^a-z0-9_]+", "_", table_name.lower()).strip("_")
        table_ref = f"{self.settings.bigquery_project_id}.{self.settings.bigquery_dataset}.{safe_table}"
        connection_clause = ""
        if self.settings.biglake_connection_id:
            connection_clause = f" WITH CONNECTION `{self.settings.biglake_connection_id}`"

        query = (
            f"CREATE OR REPLACE EXTERNAL TABLE `{table_ref}`{connection_clause} "
            f"OPTIONS (format = 'PARQUET', uris = ['{gcs_uri}'])"
        )
        client = bigquery.Client(project=self.settings.bigquery_project_id)
        client.query(query).result()
        return table_ref

    @default_retry()
    def _execute_bigquery_statement(self, statement: str) -> None:
        from google.cloud import bigquery

        client = bigquery.Client(project=self.settings.bigquery_project_id)
        client.query(statement).result()

    def _write_json_to_gcs(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._json_dumps(payload).encode("utf-8")
        local_path = self.settings.local_parquet_dir / "gcs_mirror" / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        uri = str(local_path)
        if self._gcs_enabled:
            self._upload_to_gcs(key, data)
            uri = f"gs://{self.settings.gcs_bucket}/{key}"
        return {"uri": uri, "local_path": local_path}

    def _json_dumps(self, payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, default=self._serialise, ensure_ascii=True, indent=2, sort_keys=True)

    def _normalise_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalised: dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                normalised[key] = value.isoformat()
            elif isinstance(value, Decimal):
                normalised[key] = float(value)
            elif isinstance(value, dict):
                normalised[key] = {inner_key: self._serialise(inner_value) for inner_key, inner_value in value.items()}
            elif isinstance(value, list):
                normalised[key] = [self._serialise(item) for item in value]
            else:
                normalised[key] = value
        return normalised

    def _serialise(self, value: Any) -> Any:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value
