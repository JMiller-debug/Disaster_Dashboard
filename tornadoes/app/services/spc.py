"""NOAA SPC tornado watch/warning service."""

import logging

import httpx

from app.models import TornadoCollection, TornadoFeature, TornadoProperties, TornadoType
from shared.cache import TTLCache

logger = logging.getLogger(__name__)

# NWS alerts API — filters for tornado watches and warnings globally
NWS_ALERTS = "https://api.weather.gov/alerts/active"
CACHE_TTL = 60  # tornado alerts change fast, cache for only 1 min


class SPCService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "DisasterDashboard/1.0 (contact@example.com)"},
        )
        self._cache: TTLCache[TornadoCollection] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(self) -> TornadoCollection:
        if cached := self._cache.get("tornado_alerts"):
            return cached

        # Fetch both watches and warnings in parallel
        watch_resp, warning_resp = await _fetch_parallel(
            self._client,
            f"{NWS_ALERTS}?event=Tornado+Watch",
            f"{NWS_ALERTS}?event=Tornado+Warning",
        )

        features: list[TornadoFeature] = []
        for raw_feat in watch_resp.get("features", []):
            feat = _parse_feature(raw_feat, TornadoType.WATCH)
            if feat:
                features.append(feat)
        for raw_feat in warning_resp.get("features", []):
            feat = _parse_feature(raw_feat, TornadoType.WARNING)
            if feat:
                features.append(feat)

        collection = TornadoCollection(features=features, count=len(features))
        self._cache.set("tornado_alerts", collection, CACHE_TTL)
        return collection


async def _fetch_parallel(client: httpx.AsyncClient, *urls: str) -> list[dict]:
    import asyncio

    responses = await asyncio.gather(*[client.get(u) for u in urls])
    return [r.json() for r in responses]


def _parse_feature(raw: dict, tornado_type: TornadoType) -> TornadoFeature | None:
    props = raw.get("properties", {})
    geometry = raw.get("geometry")
    if not geometry:
        return None
    return TornadoFeature(
        type="Feature",
        id=raw.get("id", ""),
        geometry=geometry,
        properties=TornadoProperties(
            event=props.get("event"),
            severity=props.get("severity"),
            certainty=props.get("certainty"),
            urgency=props.get("urgency"),
            headline=props.get("headline"),
            issued=props.get("sent"),
            expires=props.get("expires"),
            status=props.get("status"),
            type=tornado_type,
        ),
    )
