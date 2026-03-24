"""Tornadoes microservice entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from app.services.spc import SPCService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    app.state.spc = SPCService()
    yield
    await app.state.spc.close()


app = FastAPI(title="Tornadoes Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)
app.include_router(router, prefix="/api")
