from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.models.entities import EodComparison
from b3_quant_platform.schemas.eod import EodComparisonRead, MarketSnapshotBatchCreate, MarketSnapshotRead
from b3_quant_platform.services.market_data import MarketDataService

router = APIRouter(tags=["eod"])
service = MarketDataService()


@router.post("/market-snapshots", response_model=list[MarketSnapshotRead], status_code=status.HTTP_202_ACCEPTED)
def ingest_market_snapshots(
    payload: MarketSnapshotBatchCreate,
    session: Session = Depends(get_db_session),
) -> list[MarketSnapshotRead]:
    snapshots, _ = service.ingest_snapshots(session, payload)
    return snapshots


@router.get("/eod/comparisons", response_model=list[EodComparisonRead])
def list_eod_comparisons(
    reference_date: date = Query(...),
    portfolio_id: UUID | None = Query(default=None),
    scenario_slug: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[EodComparisonRead]:
    statement = select(EodComparison).where(EodComparison.reference_date == reference_date)
    if portfolio_id is not None:
        statement = statement.where(EodComparison.portfolio_id == portfolio_id)
    if scenario_slug is not None:
        statement = statement.where(EodComparison.scenario_slug == scenario_slug)
    statement = statement.order_by(EodComparison.ticker.asc())
    return list(session.scalars(statement).all())
