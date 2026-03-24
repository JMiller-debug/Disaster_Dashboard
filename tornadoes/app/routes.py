"""Tornado routes."""

from fastapi import APIRouter, HTTPException, Request

from app.models import TornadoCollection
from app.services.spc import SPCService

router = APIRouter(tags=["tornadoes"])


def _svc(request: Request) -> SPCService:
    return request.app.state.spc


@router.get("/tornadoes")
async def list_tornadoes(request: Request) -> TornadoCollection:
    try:
        return await _svc(request).fetch()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch SPC data") from exc
