"""USGS earthquake service."""

import logging

import httpx

from app.models import EarthquakeCollection, EarthquakeFeature, Magnitude, TimeWindow
from shared.cache import TTLCache

logger = logging.getLogger(__name__)

USGS_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
CACHE_TTL = 120


class USGSService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)
        self._cache: TTLCache[EarthquakeCollection] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    def _key(self, magnitude: Magnitude, window: TimeWindow) -> str:
        return f"{magnitude}_{window}"

    def _url(self, magnitude: Magnitude, window: TimeWindow) -> str:
        seg = magnitude.value if magnitude != Magnitude.ALL else "all"
        return f"{USGS_BASE}/{seg}_{window.value}.geojson"

    async def fetch(
        self,
        magnitude: Magnitude = Magnitude.ALL,
        window: TimeWindow = TimeWindow.DAY,
        min_mag: float | None = None,
    ) -> EarthquakeCollection:
        key = self._key(magnitude, window)
        if cached := self._cache.get(key):
            logger.debug("Cache hit %s", key)
            return self._filter(cached, min_mag)

        resp = await self._client.get(self._url(magnitude, window))
        resp.raise_for_status()
        raw = resp.json()

        features = [EarthquakeFeature(**f) for f in raw["features"]]
        for f in features:
            f.properties.depth = f.geometry.coordinates[2]

        collection = EarthquakeCollection(
            type=raw["type"], features=features, count=len(features)
        )
        self._cache.set(key, collection, CACHE_TTL)
        return self._filter(collection, min_mag)

    def _filter(
        self, collection: EarthquakeCollection, min_mag: float | None
    ) -> EarthquakeCollection:
        if min_mag is None:
            return collection
        filtered = [
            f
            for f in collection.features
            if f.properties.mag is not None and f.properties.mag >= min_mag
        ]
        return EarthquakeCollection(
            type=collection.type, features=filtered, count=len(filtered)
        )
