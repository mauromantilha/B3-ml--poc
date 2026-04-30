from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.api.main import app
from b3_quant_platform.api.routes import jobs as jobs_routes
from b3_quant_platform.ingestion.models import HistoricalDatasetType, SourceFileDescriptor
from b3_quant_platform.ingestion.service import HistoricalB3IngestionService
from b3_quant_platform.ingestion.validators import HistoricalIngestionValidationError
from b3_quant_platform.schemas.jobs import HistoricalIngestionRequest


def _cotahist_line(
    *,
    reference_date: date,
    ticker: str,
    trade_count: int,
    trade_quantity: int,
    trade_volume: Decimal,
    close_price: Decimal,
    market_type_code: int = 10,
    instrument_name: str = "VALE    ON",
    specification_code: str = "ON",
    isin: str = "BRVALEACNOR0",
) -> str:
    def implied(value: Decimal | None, width: int) -> str:
        if value is None:
            return "0" * width
        return f"{int((value * 100).quantize(Decimal('1'))):0{width}d}"

    return "".join(
        [
            "01",
            reference_date.strftime("%Y%m%d"),
            "02",
            f"{ticker:<12}",
            f"{market_type_code:03d}",
            f"{instrument_name:<12}",
            f"{specification_code:<10}",
            f"{'':<3}",
            "BRL ",
            implied(close_price - Decimal("1.00"), 13),
            implied(close_price + Decimal("0.80"), 13),
            implied(close_price - Decimal("1.20"), 13),
            implied(close_price - Decimal("0.10"), 13),
            implied(close_price, 13),
            implied(close_price - Decimal("0.05"), 13),
            implied(close_price + Decimal("0.05"), 13),
            f"{trade_count:05d}",
            f"{trade_quantity:018d}",
            implied(trade_volume, 18),
            "0" * 13,
            " ",
            "00000000",
            f"{1:07d}",
            "0" * 13,
            f"{isin:<12}",
            f"{1:03d}",
        ]
    )


def _cotahist_payload() -> bytes:
    lines = [
        "00COTAHIST.2026B3                20260429",
        _cotahist_line(
            reference_date=date(2026, 4, 28),
            ticker="VALE3",
            trade_count=100,
            trade_quantity=2000,
            trade_volume=Decimal("1200000.00"),
            close_price=Decimal("60.50"),
        ),
        _cotahist_line(
            reference_date=date(2026, 4, 28),
            ticker="VALE3",
            trade_count=20,
            trade_quantity=500,
            trade_volume=Decimal("500000.00"),
            close_price=Decimal("60.45"),
        ),
        _cotahist_line(
            reference_date=date(2026, 4, 28),
            ticker="PETR4",
            trade_count=80,
            trade_quantity=3000,
            trade_volume=Decimal("1500000.00"),
            close_price=Decimal("35.80"),
            instrument_name="PETROBRASPN",
            isin="BRPETRACNPR6",
        ),
        "99COTAHIST.2026B3                000000000000002",
    ]
    return ("\n".join(lines) + "\n").encode("latin-1")


def test_historical_ingestion_writes_bronze_silver_and_manifest(test_settings) -> None:
    service = HistoricalB3IngestionService(test_settings)
    descriptor = SourceFileDescriptor(
        path=Path("COTAHIST_A202604.TXT"),
        dataset_type=HistoricalDatasetType.COTAHIST,
        processing_date=date(2026, 4, 29),
    )

    result = service.ingest_bytes(_cotahist_payload(), descriptor=descriptor)

    assert result.manifest.source_record_count == 3
    assert result.manifest.deduplicated_record_count == 2
    assert result.manifest.duplicate_count == 1
    assert result.manifest.instrument_count == 2
    assert "b3/bronze/cotahist/year=2026/processing_date=2026-04-29" in str(result.bronze_local_path)
    assert any(
        "b3/silver/quotes/market_type=spot/year=2026/month=04" in str(path)
        for path in result.silver_quote_local_paths
    )

    manifest_payload = json.loads(Path(result.manifest.metadata_log_uri).read_text())
    assert manifest_payload["deduplication_rule"] == result.manifest.deduplication_rule
    assert manifest_payload["source_checksum"] == result.manifest.source_checksum


def test_historical_ingestion_rejects_invalid_price_ranges(test_settings) -> None:
    service = HistoricalB3IngestionService(test_settings)
    payload = "reference_date;ticker;market_type_code;instrument_name;specification_code;currency;open_price;high_price;low_price;average_price;close_price;best_bid_price;best_ask_price;trade_count;trade_quantity;trade_volume\n2026-04-28;VALE3;10;Vale ON;ON;BRL;60.5;59.0;61.0;60.0;60.2;60.1;60.3;10;1000;100000\n".encode(
        "latin-1"
    )
    descriptor = SourceFileDescriptor(
        path=Path("eod_quotes.csv"),
        dataset_type=HistoricalDatasetType.EOD,
        processing_date=date(2026, 4, 29),
        delimiter=";",
    )

    try:
        service.ingest_bytes(payload, descriptor=descriptor)
    except HistoricalIngestionValidationError as exc:
        assert any(issue.code == "invalid_high_price" for issue in exc.issues)
    else:
        raise AssertionError("Expected HistoricalIngestionValidationError")


def test_historical_ingestion_request_requires_input_source() -> None:
    try:
        HistoricalIngestionRequest(dataset_type="cotahist")
    except ValidationError as exc:
        assert "Either file_path or content_base64 must be provided" in str(exc)
    else:
        raise AssertionError("Expected validation error")


def test_historical_ingestion_job_route_is_idempotent(db_session, test_settings) -> None:
    jobs_routes.historical_service = HistoricalB3IngestionService(test_settings)

    def override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    payload = {
        "dataset_type": "eod",
        "processing_date": "2026-04-29",
        "reference_date": "2026-04-28",
        "source_name": "quotes.csv",
        "content_base64": base64.b64encode(
            b"reference_date;ticker;market_type_code;instrument_name;specification_code;currency;open_price;high_price;low_price;average_price;close_price;best_bid_price;best_ask_price;trade_count;trade_quantity;trade_volume;isin\n2026-04-28;VALE3;10;Vale ON;ON;BRL;60.00;61.50;59.50;60.70;60.50;60.45;60.55;100;2000;1200000;BRVALEACNOR0\n"
        ).decode("ascii"),
        "encoding": "latin-1",
        "delimiter": ";",
    }

    try:
        first = client.post("/v1/jobs/historical-ingestion", json=payload)
        second = client.post("/v1/jobs/historical-ingestion", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["details"]["reused"] is False
    assert second.json()["details"]["reused"] is True