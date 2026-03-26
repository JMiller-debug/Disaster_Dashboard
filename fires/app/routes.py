"""Fire routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.models import DayRange, FireCollection, Sensor
from app.services.firms import FIRMSService

router = APIRouter(tags=["fires"])


def _svc(request: Request) -> FIRMSService:
    return request.app.state.firms


@router.get("/fires")
async def list_fires(
    request: Request,
    sensor: Annotated[Sensor, Query(description="Satellite sensor")] = None,
    days: Annotated[DayRange, Query(description="Detection window")] = DayRange.ONE,
) -> FireCollection:
    """Endpoint listing fires."""
    try:
        return await _svc(request).fetch(sensor=sensor, days=days)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to fetch FIRMS data"
        ) from exc
