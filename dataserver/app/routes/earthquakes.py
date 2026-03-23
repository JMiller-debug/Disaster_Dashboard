"""Route for earthquakes proxy."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.earthquake import EarthquakeCollection, Magnitude, TimeWindow
from app.services.usgs import USGSService

router = APIRouter(tags=["earthquakes"])


def get_usgs(request: Request) -> USGSService:
    """Call proxy USGS service to fetch data."""
    return request.app.state.usgs


@router.get("/earthquakes")
async def list_earthquakes(
    request: Request,
    magnitude: Annotated[
        Magnitude, Query(description="USGS magnitude filter")
    ] = Magnitude.ALL,
    window: Annotated[TimeWindow, Query(description="Time window")] = TimeWindow.DAY,
    min_mag: Annotated[
        float | None, Query(ge=0, le=10, description="Client-side min magnitude filter")
    ] = None,
) -> EarthquakeCollection:
    """Return a list of earthquakes."""
    usgs = get_usgs(request)
    try:
        return await usgs.fetch(magnitude=magnitude, window=window, min_mag=min_mag)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to fetch USGS data"
        ) from exc
