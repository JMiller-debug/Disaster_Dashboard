"""
USGS Service.

A service to support fetching live earthquake data.
"""

import logging
import time

import httpx

from app.models.earthquake import (
    EarthquakeCollection,
    EarthquakeFeature,
    Magnitude,
    TimeWindow,
)

logger = logging.getLogger(__name__)

USGS_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
CACHE_TTL = 120  # seconds


class _CacheEntry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data: EarthquakeCollection, ttl: int) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl


class USGSService:
    """USGS Service Class."""

    def __init__(self) -> None:
        """Initialise class."""
        self._client = httpx.AsyncClient(timeout=10.0)
        self._cache: dict[str, _CacheEntry] = {}

    async def close(self) -> None:
        """Close connection."""
        await self._client.aclose()

    def _cache_key(self, magnitude: Magnitude, window: TimeWindow) -> str:
        return f"{magnitude}_{window}"

    def _get_cached(self, key: str) -> EarthquakeCollection | None:
        entry = self._cache.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.data
        return None

    def _build_url(self, magnitude: Magnitude, window: TimeWindow) -> str:
        mag_segment = magnitude.value if magnitude != Magnitude.ALL else "all"
        return f"{USGS_BASE}/{mag_segment}_{window.value}.geojson"

    async def fetch(
        self,
        magnitude: Magnitude = Magnitude.ALL,
        window: TimeWindow = TimeWindow.DAY,
        min_mag: float | None = None,
    ) -> EarthquakeCollection:
        """
        Docstring for fetch.

        :param self: Class function

        :param magnitude: Filter for magnitude
        :type magnitude: Magnitude

        :param window: Time Window for the query
        :type window: TimeWindow

        :param min_mag: Minimum magnitude to search for
        :type min_mag: float | None

        :return: EarthquakeCollection data
        :rtype: EarthquakeCollection
        """
        key = self._cache_key(magnitude, window)

        if cached := self._get_cached(key):
            logger.debug("Cache hit for %s", key)
            return self._apply_filters(cached, min_mag)

        url = self._build_url(magnitude, window)
        logger.info("Fetching USGS feed: %s", url)

        response = await self._client.get(url)
        response.raise_for_status()

        raw = response.json()
        features = [EarthquakeFeature(**f) for f in raw["features"]]
        collection = EarthquakeCollection(
            type=raw["type"],
            features=features,
            count=len(features),
        )

        self._cache[key] = _CacheEntry(collection, CACHE_TTL)
        return self._apply_filters(collection, min_mag)

    def _apply_filters(
        self,
        collection: EarthquakeCollection,
        min_mag: float | None,
    ) -> EarthquakeCollection:
        if min_mag is None:
            return collection

        filtered = [
            f
            for f in collection.features
            if f.properties.mag is not None and f.properties.mag >= min_mag
        ]
        return EarthquakeCollection(
            type=collection.type,
            features=filtered,
            count=len(filtered),
        )
