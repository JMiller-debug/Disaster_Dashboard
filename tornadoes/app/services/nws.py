"""NOAA NWS active tornado watch/warning service."""

import asyncio
import logging

from pydantic import ValidationError
from shared.cache import TTLCache
from shared.http import make_client

from app.models import (
    TimeWindow,
    TornadoCollection,
    TornadoFeature,
    TornadoProperties,
    TornadoType,
)

logger = logging.getLogger(__name__)

NWS_ALERTS = "https://api.weather.gov/alerts/active"
CACHE_TTL = 60


class NWSService:
    def __init__(self) -> None:
        self._client = make_client(timeout=10.0)
        self._cache: TTLCache[TornadoCollection] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(self, window: TimeWindow) -> TornadoCollection:
        cache_key = f"nws_{window}"
        if cached := self._cache.get(cache_key):
            return cached

        watch_resp, warning_resp = await asyncio.gather(
            self._client.get(f"{NWS_ALERTS}?event=Tornado+Watch"),
            self._client.get(f"{NWS_ALERTS}?event=Tornado+Warning"),
        )

        logger.info(
            "NWS raw counts — watches: %d, warnings: %d",
            len(watch_resp.json().get("features", [])),
            len(warning_resp.json().get("features", [])),
        )

        features: list[TornadoFeature] = []
        for raw in watch_resp.json().get("features", []):
            if feat := _parse_feature(raw, TornadoType.WATCH):
                features.append(feat)
        for raw in warning_resp.json().get("features", []):
            if feat := _parse_feature(raw, TornadoType.WARNING):
                features.append(feat)

        collection = TornadoCollection(
            features=features,
            count=len(features),
            source="nws",
            window=window,
        )
        self._cache.set(cache_key, collection, CACHE_TTL)
        return collection


def _parse_feature(raw: dict, tornado_type: TornadoType) -> TornadoFeature | None:
    props = raw.get("properties", {})
    geometry = raw.get("geometry")

    if geometry is None:
        logger.debug("Dropping %s — geometry is null", raw.get("id", "?"))
        return None

    try:
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
    except ValidationError as exc:
        logger.error("ValidationError for %s: %s", raw.get("id", "?"), exc)
        return None
