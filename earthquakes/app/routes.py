"""Earthquake routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.models import EarthquakeCollection, Magnitude, TimeWindow
from app.services.usgs import USGSService

router = APIRouter(tags=["earthquakes"])


def _svc(request: Request) -> USGSService:
    return request.app.state.usgs


@router.get("/earthquakes")
async def list_earthquakes(
    request: Request,
    magnitude: Annotated[Magnitude, Query()] = Magnitude.ALL,
    window: Annotated[TimeWindow, Query()] = TimeWindow.DAY,
    min_mag: Annotated[float | None, Query(ge=0, le=10)] = None,
) -> EarthquakeCollection:
    try:
        return await _svc(request).fetch(
            magnitude=magnitude, window=window, min_mag=min_mag
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to fetch USGS data"
        ) from exc
