"""Earthquake routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.models import EarthquakeCollection, TimeWindow
from app.services.usgs import USGSService

router = APIRouter(tags=["earthquakes"])


def get_usgs(request: Request) -> USGSService:
    return request.app.state.usgs


@router.get("/earthquakes")
async def list_earthquakes(
    request: Request,
    window: Annotated[TimeWindow, Query(description="Time window")] = TimeWindow.DAY,
    min_mag: Annotated[
        float,
        Query(ge=0, le=9, description="Minimum magnitude (selects optimal USGS feed)"),
    ] = 0.0,
) -> EarthquakeCollection:
    """
    Return earthquakes for the given time window.

    *min_mag* automatically selects the smallest USGS feed that covers the
    requested threshold — no redundant server-side filtering required.

    | min_mag  | Feed fetched |
    |----------|-------------|
    | >= 4.5   | 4.5_*       |
    | >= 2.5   | 2.5_*       |
    | >= 1.0   | 1.0_*       |
    | < 1.0    | all_*       |
    """
    try:
        return await get_usgs(request).fetch(window=window, min_mag=min_mag)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to fetch USGS data"
        ) from exc
