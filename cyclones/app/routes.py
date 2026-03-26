"""Cyclone routes."""

from fastapi import APIRouter, HTTPException, Request

from app.models import CycloneCollection
from app.services.nhc import NHCService

router = APIRouter(tags=["cyclones"])


def _svc(request: Request) -> NHCService:
    return request.app.state.nhc


@router.get("/cyclones")
async def list_cyclones(request: Request) -> CycloneCollection:
    """Endpoint returnging list of cylcones."""
    try:
        return await _svc(request).fetch()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch NHC data") from exc
