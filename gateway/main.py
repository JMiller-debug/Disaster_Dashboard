"""API Gateway — reverse-proxies all disaster microservices under one host."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

SERVICES: dict[str, str] = {
    "earthquakes": os.getenv("EARTHQUAKES_URL", "http://earthquakes:8001"),
    "tornadoes": os.getenv("TORNADOES_URL", "http://tornadoes:8002"),
    "cyclones": os.getenv("CYCLONES_URL", "http://cyclones:8003"),
    "fires": os.getenv("FIRES_URL", "http://fires:8004"),
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = httpx.AsyncClient(timeout=15.0)
    yield
    await app.state.client.aclose()


app = FastAPI(title="Disaster Dashboard Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/{service}/{path:path}")
async def proxy(service: str, path: str, request: Request) -> Response:
    """Forward /api/{service}/... to the matching microservice."""
    if service not in SERVICES:
        return Response(content=f"Unknown service: {service}", status_code=404)

    base = SERVICES[service]
    url = f"{base}/api/{path}"
    if qs := request.url.query:
        url = f"{url}?{qs}"

    upstream: httpx.Response = await request.app.state.client.get(url)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
