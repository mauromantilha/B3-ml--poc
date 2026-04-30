from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.api.main import app
from b3_quant_platform.api.routes import jobs as jobs_routes
from b3_quant_platform.schemas.jobs import AnalyticsMirrorRequest
from b3_quant_platform.services.analytics_mirror import AnalyticsMirrorService


def _write_source_parquet(base_dir: Path, relative_key: str, rows: list[dict[str, object]], mtime_offset: int) -> Path:
    path = base_dir / relative_key
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression="snappy")
    timestamp = (datetime(2026, 4, 29, 12, 0, 0) + timedelta(seconds=mtime_offset)).timestamp()
    path.touch()
    Path(path).chmod(0o644)
    import os

    os.utime(path, (timestamp, timestamp))
    return path


def _quotes_rows(ticker: str, checksum: str) -> list[dict[str, object]]:
    return [
        {
            "reference_date": date(2026, 4, 28),
            "processing_date": date(2026, 4, 29),
            "ticker": ticker,
            "market_type": "spot",
            "close_price": 60.5,
            "source_checksum": checksum,
        }
    ]


def test_analytics_mirror_copies_new_silver_objects_and_generates_manifest(test_settings) -> None:
    service = AnalyticsMirrorService(test_settings)
    base_dir = test_settings.local_parquet_dir
    source_key = "b3/silver/quotes/market_type=spot/year=2026/month=04/quotes_20260428_a.parquet"
    source_path = _write_source_parquet(base_dir, source_key, _quotes_rows("VALE3", "checksum-a"), 1)

    result = service.mirror_dataset(
        AnalyticsMirrorRequest(
            dataset_name="quotes",
            table_name="quotes",
            processing_date=date(2026, 4, 29),
            materialization_strategy="external_and_native",
        )
    )

    mirrored_path = test_settings.local_parquet_dir / "gcs_mirror" / "curated/external_raw_analytics/quotes/market_type=spot/year=2026/month=04/quotes_20260428_a.parquet"
    assert result.mirrored_object_count == 1
    assert result.external_table and result.external_table.endswith("quotes_ext")
    assert result.native_table and result.native_table.endswith("quotes")
    assert mirrored_path.exists()
    assert mirrored_path.read_bytes() == source_path.read_bytes()

    manifest_payload = json.loads(result.local_path.read_text())
    assert manifest_payload["mirrored_object_count"] == 1
    assert manifest_payload["lineage"][0]["source_key"] == source_key
    assert manifest_payload["ddl_statements"]["external_table_sql"]
    assert manifest_payload["dml_statements"]["native_merge_sql"]


def test_analytics_mirror_uses_watermark_for_incremental_copy(test_settings) -> None:
    service = AnalyticsMirrorService(test_settings)
    base_dir = test_settings.local_parquet_dir
    _write_source_parquet(
        base_dir,
        "b3/silver/quotes/market_type=spot/year=2026/month=04/quotes_20260428_a.parquet",
        _quotes_rows("VALE3", "checksum-a"),
        1,
    )

    first = service.mirror_dataset(
        AnalyticsMirrorRequest(dataset_name="quotes", table_name="quotes", processing_date=date(2026, 4, 29))
    )
    second = service.mirror_dataset(
        AnalyticsMirrorRequest(dataset_name="quotes", table_name="quotes", processing_date=date(2026, 4, 29))
    )
    _write_source_parquet(
        base_dir,
        "b3/silver/quotes/market_type=spot/year=2026/month=04/quotes_20260428_b.parquet",
        _quotes_rows("PETR4", "checksum-b"),
        2,
    )
    third = service.mirror_dataset(
        AnalyticsMirrorRequest(dataset_name="quotes", table_name="quotes", processing_date=date(2026, 4, 29))
    )

    assert first.mirrored_object_count == 1
    assert second.mirrored_object_count == 0
    assert third.mirrored_object_count == 1


def test_analytics_mirror_job_route_is_idempotent(db_session, test_settings) -> None:
    jobs_routes.mirror_service = AnalyticsMirrorService(test_settings)
    _write_source_parquet(
        test_settings.local_parquet_dir,
        "b3/silver/quotes/market_type=spot/year=2026/month=04/quotes_20260428_route.parquet",
        _quotes_rows("ITUB4", "checksum-route"),
        1,
    )

    def override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    payload = {
        "dataset_name": "quotes",
        "table_name": "quotes",
        "processing_date": "2026-04-29",
    }
    try:
        first = client.post("/v1/jobs/analytics-mirror", json=payload)
        second = client.post("/v1/jobs/analytics-mirror", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["details"]["reused"] is False
    assert first.json()["details"]["mirrored_object_count"] == 1
    assert second.json()["details"]["reused"] is True