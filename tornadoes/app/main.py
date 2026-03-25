"""Tornadoes microservice entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from app.services.nws import NWSService
from app.services.spc import SPCService
from app.services.swdi import SWDIService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """`Lifespan` context manager handler."""
    app.state.nws = NWSService()
    app.state.spc = SPCService()
    app.state.swdi = SWDIService()  # Initialize SWDI
    yield
    await app.state.nws.close()
    await app.state.spc.close()
    await app.state.swdi.close()


app = FastAPI(title="Tornadoes Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)
app.include_router(router, prefix="/api")
