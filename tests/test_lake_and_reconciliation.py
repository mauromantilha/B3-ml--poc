from __future__ import annotations

from datetime import date
from decimal import Decimal

from b3_quant_platform.schemas.eod import MarketSnapshotBatchCreate
from b3_quant_platform.schemas.jobs import EodReconcileRequest
from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate
from b3_quant_platform.services.eod_reconciliation import EodReconciliationService
from b3_quant_platform.services.lake_writer import LakeWriterService
from b3_quant_platform.services.market_data import MarketDataService
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService


def test_lake_writer_partitions_by_date_market_ticker(test_settings) -> None:
    writer = LakeWriterService(test_settings)

    result = writer.write_records(
        [{"ticker": "VALE3", "close_price": Decimal("61.23")}],
        layer="raw",
        reference_date=date(2026, 4, 28),
        market="equities",
        ticker="VALE3",
        artifact_name="market_eod",
    )

    assert result.local_path.exists()
    assert "date=2026-04-28/market=equities/ticker=VALE3" in str(result.local_path)


def test_reconcile_eod_is_idempotent(db_session, test_settings) -> None:
    portfolio_service = PortfolioFactoryService()
    portfolio_service.seed_default_templates(db_session)
    template = portfolio_service.list_templates(db_session)[0]
    portfolio = portfolio_service.create_instance(
        db_session,
        PortfolioInstanceCreate(
            template_id=template.id,
            name="Reconcile Book",
            reference_date=date(2026, 4, 28),
            seed_capital=Decimal("100000.00"),
            positions=[
                {
                    "ticker": "VALE3",
                    "market": "equities",
                    "target_weight": "0.5",
                    "quantity": "100",
                    "close_price": "60.00",
                    "signal": {},
                },
                {
                    "ticker": "PETR4",
                    "market": "equities",
                    "target_weight": "0.5",
                    "quantity": "150",
                    "close_price": "35.00",
                    "signal": {},
                },
            ],
        ),
    )

    market_service = MarketDataService(LakeWriterService(test_settings))
    market_service.ingest_snapshots(
        db_session,
        MarketSnapshotBatchCreate(
            reference_date=date(2026, 4, 28),
            snapshots=[
                {
                    "ticker": "VALE3",
                    "market": "equities",
                    "open_price": "59.00",
                    "high_price": "61.50",
                    "low_price": "58.90",
                    "close_price": "60.50",
                    "adjusted_close": "60.50",
                    "volume": 1000000,
                    "source_version": "b3-eod-v1",
                },
                {
                    "ticker": "PETR4",
                    "market": "equities",
                    "open_price": "34.00",
                    "high_price": "36.20",
                    "low_price": "33.80",
                    "close_price": "35.80",
                    "adjusted_close": "35.80",
                    "volume": 2000000,
                    "source_version": "b3-eod-v1",
                },
            ],
        ),
    )

    service = EodReconciliationService(LakeWriterService(test_settings))
    service.settings = test_settings
    payload = EodReconcileRequest(
        reference_date=date(2026, 4, 28),
        portfolio_id=portfolio.id,
        expected_prices=[
            {"ticker": "VALE3", "expected_close": "60.00"},
            {"ticker": "PETR4", "expected_close": "35.50"},
        ],
    )

    first_job_run, first_details = service.reconcile(db_session, payload)
    second_job_run, second_details = service.reconcile(db_session, payload)

    assert first_job_run.id == second_job_run.id
    assert first_details["comparison_count"] == 2
    assert second_details["reused"] is True
