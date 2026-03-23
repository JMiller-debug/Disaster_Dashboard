"""Main.py entry point for the fastapi app."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import earthquakes
from app.services.usgs import USGSService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any, None]:
    """
    Docstring for lifespan.

    :param app: Fast API application
    :type app: FastAPI

    Returns an AsyncGenerator of the USGS Service
    """
    app.state.usgs = USGSService()
    yield
    await app.state.usgs.close()


app = FastAPI(title="Earthquake Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(earthquakes.router, prefix="/api")
