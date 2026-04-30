from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.schemas.portfolio import (
    PortfolioInstanceCreate,
    PortfolioInstanceRead,
    PortfolioTemplateCreate,
    PortfolioTemplateRead,
    SeedTemplatesResponse,
)
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService

router = APIRouter(tags=["portfolios"])
service = PortfolioFactoryService()


@router.post("/templates/seed", response_model=SeedTemplatesResponse, status_code=status.HTTP_202_ACCEPTED)
def seed_templates(session: Session = Depends(get_db_session)) -> SeedTemplatesResponse:
    created, skipped, templates = service.seed_default_templates(session)
    return SeedTemplatesResponse(created=created, skipped=skipped, templates=templates)


@router.get("/templates", response_model=list[PortfolioTemplateRead])
def list_templates(session: Session = Depends(get_db_session)) -> list[PortfolioTemplateRead]:
    return service.list_templates(session)


@router.post("/templates", response_model=PortfolioTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: PortfolioTemplateCreate,
    session: Session = Depends(get_db_session),
) -> PortfolioTemplateRead:
    return service.create_template(session, payload)


@router.get("/portfolios", response_model=list[PortfolioInstanceRead])
def list_portfolios(session: Session = Depends(get_db_session)) -> list[PortfolioInstanceRead]:
    return service.list_portfolios(session)


@router.post("/portfolios", response_model=PortfolioInstanceRead, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioInstanceCreate,
    session: Session = Depends(get_db_session),
) -> PortfolioInstanceRead:
    try:
        return service.create_instance(session, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
