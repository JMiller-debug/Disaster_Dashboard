"""Shared httpx client factory with request/response logging."""

import logging
import time

import httpx

logger = logging.getLogger("http.outbound")


async def _log_request(request: httpx.Request) -> None:
    request.extensions["_t"] = time.monotonic()
    logger.info("--> %s %s", request.method, request.url)


async def _log_response(response: httpx.Response) -> None:
    elapsed = time.monotonic() - response.request.extensions.get("_t", time.monotonic())
    logger.info(
        "<-- %s %s %d (%.0fms)",
        response.request.method,
        response.request.url,
        response.status_code,
        elapsed * 1000,
    )


def make_client(**kwargs) -> httpx.AsyncClient:
    """Return an AsyncClient with outbound request/response logging pre-wired."""
    event_hooks = kwargs.pop("event_hooks", {})
    merged_hooks = {
        "request": [_log_request, *event_hooks.get("request", [])],
        "response": [_log_response, *event_hooks.get("response", [])],
    }
    return httpx.AsyncClient(event_hooks=merged_hooks, **kwargs)
