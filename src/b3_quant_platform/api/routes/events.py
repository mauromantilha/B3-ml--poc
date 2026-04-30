from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.schemas.scenario import (
    EventAssetMappingCreate,
    EventAssetMappingRead,
    EventCatalogCreate,
    EventCatalogRead,
    EventImpactProfileCreate,
    EventImpactProfileRead,
    ShockVectorRead,
)
from b3_quant_platform.services.event_catalog import EventCatalogService

router = APIRouter(tags=["events"])
service = EventCatalogService()


@router.get("/events", response_model=list[EventCatalogRead])
def list_events(session: Session = Depends(get_db_session)) -> list[EventCatalogRead]:
    return service.list_events(session)


@router.get("/events/{event_id}", response_model=EventCatalogRead)
def get_event(event_id: UUID, session: Session = Depends(get_db_session)) -> EventCatalogRead:
    event = service.get_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.post("/events", response_model=EventCatalogRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCatalogCreate,
    session: Session = Depends(get_db_session),
) -> EventCatalogRead:
    return service.create_event(session, payload)


@router.post("/events/{event_id}/assets", response_model=EventAssetMappingRead, status_code=status.HTTP_201_CREATED)
def add_asset_mapping(
    event_id: UUID,
    payload: EventAssetMappingCreate,
    session: Session = Depends(get_db_session),
) -> EventAssetMappingRead:
    try:
        return service.add_asset_mapping(session, event_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/events/{event_id}/impact-profiles",
    response_model=EventImpactProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def add_impact_profile(
    event_id: UUID,
    payload: EventImpactProfileCreate,
    session: Session = Depends(get_db_session),
) -> EventImpactProfileRead:
    try:
        return service.add_impact_profile(session, event_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/events/{event_id}/shock-vector", response_model=ShockVectorRead)
def get_shock_vector(
    event_id: UUID,
    impact_profile_id: UUID | None = None,
    session: Session = Depends(get_db_session),
) -> ShockVectorRead:
    try:
        return ShockVectorRead(**service.event_to_shock_vector(session, event_id, impact_profile_id=impact_profile_id))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error