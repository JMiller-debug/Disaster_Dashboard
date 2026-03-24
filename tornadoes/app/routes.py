"""Tornado routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.models import TimeWindow, TornadoCollection
from app.services.nws import NWSService
from app.services.spc import SPCService
from app.services.swdi import SWDIService  # Update import

router = APIRouter(tags=["tornadoes"])


def _nws(request: Request) -> NWSService:
    return request.app.state.nws


def _spc(request: Request) -> SPCService:
    return request.app.state.spc


def _swdi(request: Request) -> SWDIService:
    return request.app.state.swdi


@router.get("/tornadoes")
async def list_tornadoes(
    request: Request,
    window: Annotated[TimeWindow, Query(description="Time window")] = TimeWindow.DAY,
) -> TornadoCollection:
    try:
        # Live NWS alerts for < 24 hours
        if window in (TimeWindow.HOUR, TimeWindow.DAY):
            return await _nws(request).fetch(window)

        # New SWDI JSON API for historical windows (Week/Month)
        return await _swdi(request).fetch(window)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to fetch tornado data"
        ) from exc
