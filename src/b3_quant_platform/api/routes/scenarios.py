from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.schemas.scenario import (
    CounterfactualRunRead,
    CounterfactualRunRequest,
    EventScenarioFromEventCreate,
    ScenarioDefinitionCreate,
    ScenarioDefinitionRead,
    ScenarioRunRead,
    ScenarioRunRequest,
)
from b3_quant_platform.services.event_catalog import EventCatalogService
from b3_quant_platform.services.scenario_lab import ScenarioLabService

router = APIRouter(tags=["scenarios"])
service = ScenarioLabService()
event_service = EventCatalogService()


@router.post("/scenarios", response_model=ScenarioDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioDefinitionCreate,
    session: Session = Depends(get_db_session),
) -> ScenarioDefinitionRead:
    return service.create_scenario(session, payload)


@router.post("/scenarios/run", response_model=ScenarioRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_scenario(
    payload: ScenarioRunRequest,
    session: Session = Depends(get_db_session),
) -> ScenarioRunRead:
    try:
        return service.run_scenario(session, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/scenarios/from-event", response_model=ScenarioDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_scenario_from_event(
    payload: EventScenarioFromEventCreate,
    session: Session = Depends(get_db_session),
) -> ScenarioDefinitionRead:
    try:
        return event_service.create_scenario_from_event(session, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/scenarios/counterfactual-run", response_model=CounterfactualRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_counterfactual(
    payload: CounterfactualRunRequest,
    session: Session = Depends(get_db_session),
) -> CounterfactualRunRead:
    try:
        return event_service.run_counterfactual(session, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
