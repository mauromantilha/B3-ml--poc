from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from b3_quant_platform.core.config import get_settings
from b3_quant_platform.core.idempotency import build_idempotency_key, get_existing_job_run
from b3_quant_platform.models.entities import EodComparison, JobRun, MarketEodSnapshot, PortfolioInstance
from b3_quant_platform.models.enums import ComparisonVerdict, RunStatus
from b3_quant_platform.schemas.jobs import EodReconcileRequest
from b3_quant_platform.services.lake_writer import LakeWriterService


class EodReconciliationService:
    def __init__(self, lake_writer: LakeWriterService | None = None) -> None:
        self.lake_writer = lake_writer or LakeWriterService()
        self.settings = get_settings()

    def reconcile(self, session: Session, payload: EodReconcileRequest) -> tuple[JobRun, dict[str, Any]]:
        idempotency_key = build_idempotency_key(
            "eod_reconcile",
            payload.reference_date,
            payload.model_dump(mode="json"),
        )
        existing_job = get_existing_job_run(session, idempotency_key)
        if existing_job is not None and existing_job.status == RunStatus.SUCCEEDED:
            return existing_job, self._existing_summary(session, payload)

        portfolio = session.get(PortfolioInstance, payload.portfolio_id)
        if portfolio is None:
            raise ValueError("Portfolio not found")

        job_run = existing_job or JobRun(
            job_name="eod_reconcile",
            reference_date=payload.reference_date,
            idempotency_key=idempotency_key,
            status=RunStatus.RUNNING,
            payload_json=payload.model_dump(mode="json"),
        )
        session.add(job_run)
        session.flush()

        expected_by_ticker = {item.ticker: Decimal(item.expected_close) for item in payload.expected_prices}
        snapshots = list(
            session.scalars(
                select(MarketEodSnapshot).where(
                    MarketEodSnapshot.reference_date == payload.reference_date,
                    MarketEodSnapshot.ticker.in_(tuple(expected_by_ticker.keys())),
                )
            ).all()
        )
        actual_by_ticker = {snapshot.ticker: snapshot for snapshot in snapshots}

        missing = sorted(set(expected_by_ticker).difference(actual_by_ticker))
        if missing:
            raise ValueError(f"Missing market snapshots for tickers: {', '.join(missing)}")

        rows: list[dict[str, Any]] = []
        tracking_errors: list[Decimal] = []
        for ticker, expected_close in expected_by_ticker.items():
            actual_close = Decimal(actual_by_ticker[ticker].close_price)
            tracking_error_bps = self._tracking_error_bps(expected_close, actual_close)
            verdict = self._resolve_verdict(expected_close, actual_close, tracking_error_bps)
            comparison = session.scalar(
                select(EodComparison).where(
                    EodComparison.portfolio_id == payload.portfolio_id,
                    EodComparison.reference_date == payload.reference_date,
                    EodComparison.ticker == ticker,
                    EodComparison.scenario_slug == payload.scenario_slug,
                )
            )
            details = {
                "expected_close": float(expected_close),
                "actual_close": float(actual_close),
                "abs_delta": float(abs(actual_close - expected_close)),
            }
            if comparison is None:
                comparison = EodComparison(
                    portfolio_id=payload.portfolio_id,
                    reference_date=payload.reference_date,
                    ticker=ticker,
                    scenario_slug=payload.scenario_slug,
                    expected_close=expected_close,
                    actual_close=actual_close,
                    tracking_error_bps=tracking_error_bps,
                    verdict=verdict,
                    comparison_details_json=details,
                )
                session.add(comparison)
            else:
                comparison.expected_close = expected_close
                comparison.actual_close = actual_close
                comparison.tracking_error_bps = tracking_error_bps
                comparison.verdict = verdict
                comparison.comparison_details_json = details

            rows.append(
                {
                    "portfolio_id": str(payload.portfolio_id),
                    "reference_date": payload.reference_date,
                    "ticker": ticker,
                    "scenario_slug": payload.scenario_slug,
                    "expected_close": expected_close,
                    "actual_close": actual_close,
                    "tracking_error_bps": tracking_error_bps,
                    "verdict": verdict.value,
                }
            )
            tracking_errors.append(abs(tracking_error_bps))

        result = self.lake_writer.write_records(
            rows,
            layer="curated",
            reference_date=payload.reference_date,
            market=self.settings.default_market,
            ticker="MULTI",
            artifact_name=f"eod_comparisons_{payload.scenario_slug}",
        )

        job_run.status = RunStatus.SUCCEEDED
        job_run.result_uri = result.storage_uri
        session.flush()

        avg_error = float(sum(tracking_errors) / len(tracking_errors)) if tracking_errors else 0.0
        return job_run, {
            "portfolio_id": str(payload.portfolio_id),
            "reference_date": payload.reference_date.isoformat(),
            "scenario_slug": payload.scenario_slug,
            "comparison_count": len(rows),
            "mean_abs_tracking_error_bps": avg_error,
            "artifact_uri": result.storage_uri,
            "reused": False,
        }

    def _existing_summary(self, session: Session, payload: EodReconcileRequest) -> dict[str, Any]:
        rows = list(
            session.scalars(
                select(EodComparison).where(
                    EodComparison.portfolio_id == payload.portfolio_id,
                    EodComparison.reference_date == payload.reference_date,
                    EodComparison.scenario_slug == payload.scenario_slug,
                )
            ).all()
        )
        mean_abs_error = 0.0
        if rows:
            mean_abs_error = float(
                sum(abs(Decimal(row.tracking_error_bps)) for row in rows) / Decimal(len(rows))
            )
        return {
            "portfolio_id": str(payload.portfolio_id),
            "reference_date": payload.reference_date.isoformat(),
            "scenario_slug": payload.scenario_slug,
            "comparison_count": len(rows),
            "mean_abs_tracking_error_bps": mean_abs_error,
            "artifact_uri": None,
            "reused": True,
        }

    @staticmethod
    def _tracking_error_bps(expected_close: Decimal, actual_close: Decimal) -> Decimal:
        if expected_close == 0:
            return Decimal("0")
        return ((actual_close - expected_close) / expected_close) * Decimal("10000")

    @staticmethod
    def _resolve_verdict(
        expected_close: Decimal,
        actual_close: Decimal,
        tracking_error_bps: Decimal,
    ) -> ComparisonVerdict:
        if abs(tracking_error_bps) <= Decimal("25"):
            return ComparisonVerdict.INLINE
        if actual_close > expected_close:
            return ComparisonVerdict.OUTPERFORMED
        return ComparisonVerdict.UNDERPERFORMED
