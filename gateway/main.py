"""Thin gateway for the natural disaster microservices."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any  # still used in type hints for schema dicts

import httpx
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

SERVICES: dict[str, str] = {
    "earthquakes": "http://earthquakes:8001",
    "tornadoes": "http://tornadoes:8002",
    "cyclones": "http://cyclones:8003",
    "fires": "http://fires:8004",
}


async def refresh_openapi_docs(app: FastAPI) -> dict[str, Any]:
    """
    Aggregate OpenAPI schemas from all downstream microservices.

    Each service's paths are remapped from e.g. `/api/earthquakes` →
    `/api/earthquakes/earthquakes` so that the gateway path
    `/api/{service}/{path}` resolves correctly.

    Schema component names are namespaced per service (e.g.
    `EarthquakeCollection` → `earthquakes__EarthquakeCollection`) to
    prevent collisions when multiple services share model names.
    """
    logger.info("Refreshing OpenAPI schema from %d services", len(SERVICES))

    # Base schema from gateway's own routes only (admin endpoints etc.)
    schema: dict[str, Any] = get_openapi(
        title="Disaster Dashboard — Unified API",
        version="1.0.0",
        description=(
            "Aggregated API gateway for all disaster-monitoring microservices.\n\n"
            "Routes follow the pattern `/api/{service}/...` and are proxied "
            "transparently to the relevant microservice."
        ),
        routes=app.routes,
    )
    schema.setdefault("paths", {})
    schema.setdefault("components", {"schemas": {}})
    schema["components"].setdefault("schemas", {})

    # Track which services responded so we can surface health info
    service_status: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_service_schema(client, name, base_url)
                for name, base_url in SERVICES.items()
            ],
            return_exceptions=True,
        )

    for name, result in zip(SERVICES.keys(), results, strict=True):
        if isinstance(result, Exception):
            logger.error("Failed to fetch schema for %s: %s", name, result)
            service_status[name] = f"unreachable ({type(result).__name__})"
            continue

        service_schema: dict[str, Any] = result
        service_status[name] = "ok"

        # ------------------------------------------------------------------
        # 1. Namespace component schemas:  Foo → {service}__Foo
        # ------------------------------------------------------------------
        raw_schemas: dict[str, Any] = service_schema.get("components", {}).get(
            "schemas", {}
        )
        name_map: dict[str, str] = {}  # old → new ref name
        for model_name, model_schema in raw_schemas.items():
            namespaced = f"{name}__{model_name}"
            name_map[model_name] = namespaced
            schema["components"]["schemas"][namespaced] = model_schema

        # ------------------------------------------------------------------
        # 2. Rewrite $ref strings inside the merged schemas
        # ------------------------------------------------------------------
        for namespaced_name in list(name_map.values()):
            _rewrite_refs(schema["components"]["schemas"][namespaced_name], name_map)

        # ------------------------------------------------------------------
        # 3. Remap paths and rewrite $refs inside path operations
        #
        #    Service path:  /api/earthquakes   (from its own OpenAPI)
        #    Gateway path:  /api/earthquakes/earthquakes
        #
        #    General rule:  /api/{tail}  →  /api/{service}/{tail_without_leading_api/}
        #    Simpler rule used here: strip leading /api from service path,
        #    prepend /api/{service}.
        # ------------------------------------------------------------------
        for path, methods in service_schema.get("paths", {}).items():
            # Strip a leading /api segment if present so we don't double it.
            # e.g.  /api/earthquakes  →  /earthquakes
            #       /earthquakes      →  /earthquakes  (already clean)
            tail = path.removeprefix("/api")
            gateway_path = f"/api/{name}{tail}"

            # Namespace operationIds and $refs inside each operation
            rewritten_methods: dict[str, Any] = {}
            for method, operation in methods.items():
                op = dict(operation)
                # Prefix operationId to avoid collisions
                if "operationId" in op:
                    op["operationId"] = f"{name}__{op['operationId']}"
                # Ensure the service tag is present
                op.setdefault("tags", [])
                if name not in op["tags"]:
                    op["tags"] = [name, *op["tags"]]
                # Rewrite $refs in request/response bodies
                _rewrite_refs(op, name_map)
                rewritten_methods[method] = op

            schema["paths"][gateway_path] = rewritten_methods

    # Attach service health summary as an extension field
    schema["x-service-status"] = service_status

    app.openapi_schema = schema
    logger.info(
        "Schema refreshed — %d paths, services: %s",
        len(schema["paths"]),
        service_status,
    )
    return schema


async def _fetch_service_schema(
    client: httpx.AsyncClient, base_url: str
) -> dict[str, Any]:
    """Fetch and return the raw OpenAPI JSON from a single microservice."""
    url = f"{base_url}/openapi.json"
    logger.debug("Fetching schema: %s", url)
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


def _rewrite_refs(obj: Any, name_map: dict[str, str]) -> None:  # noqa: ANN401
    """
    Recursively rewrite ``$ref`` values in-place.

    ``#/components/schemas/Foo`` becomes
    ``#/components/schemas/{service}__Foo`` using *name_map*.
    """
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref: str = obj["$ref"]
            prefix = "#/components/schemas/"
            if ref.startswith(prefix):
                original = ref[len(prefix) :]
                if original in name_map:
                    obj["$ref"] = f"{prefix}{name_map[original]}"
        for value in obj.values():
            _rewrite_refs(value, name_map)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_refs(item, name_map)


async def _discovery_loop(app: FastAPI) -> None:
    """Background task: re-sync docs from all services every 60 s."""
    await asyncio.sleep(5)  # let services finish booting first
    while True:
        try:
            await refresh_openapi_docs(app)
        except Exception:
            logger.exception("Error in discovery loop")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """`Lifespan` context manager handler."""
    # Shared client for all proxied requests — persistent connection pools per host
    app.state.proxy_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        await refresh_openapi_docs(app)
    except Exception:  # noqa: BLE001
        logger.warning("Initial schema sync failed — background task will retry")

    task = asyncio.create_task(_discovery_loop(app))
    yield
    task.cancel()
    await app.state.proxy_client.aclose()


app = FastAPI(
    title="Disaster Dashboard — Unified API",
    lifespan=lifespan,
    # Return the cached schema directly; refreshed out-of-band.
    openapi_url="/openapi.json",
)


def _openapi_override() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    # Fallback: build a minimal schema if nothing has been cached yet.
    return get_openapi(title=app.title, version="1.0.0", routes=app.routes)


app.openapi = _openapi_override  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Proxy route — must come *after* admin routes so it doesn't shadow them
# ---------------------------------------------------------------------------


@app.post("/admin/refresh-docs", tags=["Admin"])
async def manual_refresh(request: Request) -> JSONResponse:
    """Manually trigger an OpenAPI schema re-sync from all microservices."""
    schema = await refresh_openapi_docs(request.app)
    return JSONResponse(
        {
            "status": "ok",
            "paths_synced": len(schema["paths"]),
            "service_status": schema.get("x-service-status", {}),
        }
    )


@app.get("/admin/service-status", tags=["Admin"])
async def service_status() -> JSONResponse:
    """Return the last-known health of each downstream microservice."""
    return JSONResponse(
        app.openapi_schema.get("x-service-status", {})
        if app.openapi_schema
        else {"error": "schema not yet loaded"}
    )


@app.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def proxy(service: str, path: str, request: Request) -> Response:
    """Transparent proxy to the appropriate microservice."""
    if service not in SERVICES:
        return JSONResponse(
            {
                "error": f"Unknown service '{service}'. "
                f"Available: {list(SERVICES.keys())}"
            },
            status_code=404,
        )

    target_url = f"{SERVICES[service]}/api/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Strip hop-by-hop headers that must not be forwarded
    HOP_BY_HOP = {  # noqa: N806
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailers",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }

    client: httpx.AsyncClient = request.app.state.proxy_client
    upstream = await client.request(
        method=request.method,
        url=target_url,
        headers=headers,
        content=await request.body(),
    )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )
