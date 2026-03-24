import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi_proxy_lib.core.http import ProxyWebService

# Setup Logging - ensure it catches everything
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

SERVICES: dict[str, str] = {
    "earthquakes": "http://earthquakes:8001",
    "tornadoes": "http://tornadoes:8002",
    "cyclones": "http://cyclones:8003",
    "fires": "http://fires:8004",
}


async def refresh_openapi_docs(app: FastAPI):
    """Aggregate OpenAPI schemas from all microservices."""
    logger.info("🔄 Starting OpenAPI schema aggregation...")

    # 1. Start with the Gateway's own routes
    new_schema = get_openapi(
        title="Disaster Dashboard Unified API",
        version="1.0.0",
        routes=app.routes,  # This picks up /admin/refresh-docs
    )

    if "components" not in new_schema:
        new_schema["components"] = {"schemas": {}}

    # We use a fresh client here to avoid any pooling issues during doc sync
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, base_url in SERVICES.items():
            url = f"{base_url}/openapi.json"
            try:
                logger.info(f"🔍 Fetching docs from {name} at {url}")
                resp = await client.get(url)

                if resp.status_code == 200:
                    service_docs = resp.json()

                    # Merge Paths
                    for path, methods in service_docs.get("paths", {}).items():
                        # Standardize path: /api/tornadoes + /tornadoes = /api/tornadoes/tornadoes
                        gateway_path = f"/api/{name}{path}"
                        new_schema["paths"][gateway_path] = methods

                    # Merge Schemas
                    service_schemas = service_docs.get("components", {}).get(
                        "schemas", {}
                    )
                    new_schema["components"]["schemas"].update(service_schemas)

                    logger.info(f"✅ Successfully synced docs for: {name}")
                else:
                    logger.warning(
                        f"⚠️ {name} returned {resp.status_code} - logic may be incorrect"
                    )
            except Exception as e:
                logger.error(f"❌ Failed to reach {name}: {type(e).__name__}")

    # CRITICAL: Directly set the schema on the app object
    app.openapi_schema = new_schema
    return new_schema


async def discovery_loop(app: FastAPI):
    # Small delay to let microservices boot up first in Docker/Local
    await asyncio.sleep(5)
    while True:
        try:
            await refresh_openapi_docs(app)
        except Exception as e:
            logger.error(f"Critical error in discovery loop: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.proxy_service = ProxyWebService()

    # Run once at startup so docs are ready immediately
    # We wrap in a try/except so if services are down, Gateway still starts
    try:
        await refresh_openapi_docs(app)
    except Exception:
        logger.warning("Initial doc sync failed. Background task will retry.")

    bg_task = asyncio.create_task(discovery_loop(app))
    yield
    bg_task.cancel()


app = FastAPI(lifespan=lifespan)

# Overriding the default openapi method to return our custom schema
app.openapi = lambda: (
    app.openapi_schema if app.openapi_schema else refresh_openapi_docs(app)
)


@app.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    include_in_schema=False,
)
async def proxy(service: str, path: str, request: Request):
    if service not in SERVICES:
        return JSONResponse(
            {"error": f"Service '{service}' not found"}, status_code=404
        )

    target_url = f"{SERVICES[service]}/api/{path}"
    proxy_service: ProxyWebService = request.app.state.proxy_service
    return await proxy_service.proxy(request, target_url)


@app.post("/admin/refresh-docs", tags=["Admin"])
async def manual_refresh(request: Request):
    schema = await refresh_openapi_docs(request.app)
    return {"status": "success", "endpoints_synced": list(schema["paths"].keys())}
