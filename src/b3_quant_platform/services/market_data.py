from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from b3_quant_platform.models.entities import MarketEodSnapshot
from b3_quant_platform.schemas.eod import MarketSnapshotBatchCreate
from b3_quant_platform.services.lake_writer import LakeWriterService


class MarketDataService:
    def __init__(self, lake_writer: LakeWriterService | None = None) -> None:
        self.lake_writer = lake_writer or LakeWriterService()

    def ingest_snapshots(self, session: Session, payload: MarketSnapshotBatchCreate) -> tuple[list[MarketEodSnapshot], list[str]]:
        upserted: list[MarketEodSnapshot] = []
        grouped_records: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

        for snapshot_payload in payload.snapshots:
            ingest_hash = self._build_ingest_hash(
                payload.reference_date,
                snapshot_payload.market,
                snapshot_payload.ticker,
                snapshot_payload.source_version,
                snapshot_payload.close_price,
            )
            existing = session.scalar(
                select(MarketEodSnapshot).where(
                    MarketEodSnapshot.reference_date == payload.reference_date,
                    MarketEodSnapshot.market == snapshot_payload.market,
                    MarketEodSnapshot.ticker == snapshot_payload.ticker,
                )
            )

            if existing is None:
                existing = MarketEodSnapshot(
                    reference_date=payload.reference_date,
                    market=snapshot_payload.market,
                    ticker=snapshot_payload.ticker,
                    open_price=snapshot_payload.open_price,
                    high_price=snapshot_payload.high_price,
                    low_price=snapshot_payload.low_price,
                    close_price=snapshot_payload.close_price,
                    adjusted_close=snapshot_payload.adjusted_close,
                    volume=snapshot_payload.volume,
                    source_version=snapshot_payload.source_version,
                    ingest_hash=ingest_hash,
                )
                session.add(existing)
            else:
                existing.open_price = snapshot_payload.open_price
                existing.high_price = snapshot_payload.high_price
                existing.low_price = snapshot_payload.low_price
                existing.close_price = snapshot_payload.close_price
                existing.adjusted_close = snapshot_payload.adjusted_close
                existing.volume = snapshot_payload.volume
                existing.source_version = snapshot_payload.source_version
                existing.ingest_hash = ingest_hash

            grouped_records[(snapshot_payload.market, snapshot_payload.ticker)].append(
                {
                    "reference_date": payload.reference_date,
                    "ticker": snapshot_payload.ticker,
                    "market": snapshot_payload.market,
                    "open_price": Decimal(snapshot_payload.open_price),
                    "high_price": Decimal(snapshot_payload.high_price),
                    "low_price": Decimal(snapshot_payload.low_price),
                    "close_price": Decimal(snapshot_payload.close_price),
                    "adjusted_close": Decimal(snapshot_payload.adjusted_close),
                    "volume": snapshot_payload.volume,
                    "source_version": snapshot_payload.source_version,
                    "ingest_hash": ingest_hash,
                }
            )
            upserted.append(existing)

        session.flush()

        artifacts: list[str] = []
        for (market, ticker), records in grouped_records.items():
            result = self.lake_writer.write_records(
                records,
                layer="raw",
                reference_date=payload.reference_date,
                market=market,
                ticker=ticker,
                artifact_name="market_eod",
            )
            artifacts.append(result.storage_uri)

        return upserted, artifacts

    @staticmethod
    def _build_ingest_hash(
        reference_date: date,
        market: str,
        ticker: str,
        source_version: str,
        close_price: Decimal,
    ) -> str:
        raw = f"{reference_date.isoformat()}:{market}:{ticker}:{source_version}:{close_price}"
        return hashlib.sha256(raw.encode()).hexdigest()
