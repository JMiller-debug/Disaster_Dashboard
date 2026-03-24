"""USGS Service — fetches live earthquake data with smart feed selection."""

import logging
import time

import httpx
from shared.cache import TTLCache

from app.models import EarthquakeCollection, EarthquakeFeature, TimeWindow

logger = logging.getLogger(__name__)

USGS_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
CACHE_TTL = 120  # seconds

# USGS feed thresholds in descending order.
# We pick the first feed whose floor is <= the requested min_mag,
# which gives us the smallest payload that still contains all relevant quakes.
_FEED_THRESHOLDS: list[tuple[float, str]] = [
    (4.5, "4.5"),
    (2.5, "2.5"),
    (1.0, "1.0"),
    (0.0, "all"),
]


def _feed_for_min_mag(min_mag: float) -> str:
    """Return the tightest USGS feed segment that covers *min_mag*."""
    for threshold, segment in _FEED_THRESHOLDS:
        if min_mag >= threshold:
            return segment
    return "all"


class _CacheEntry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data: EarthquakeCollection, ttl: int) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl


class USGSService:
    """Fetches and caches USGS earthquake feeds."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)
        self._cache: TTLCache[EarthquakeCollection] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    def _cache_key(self, feed: str, window: TimeWindow) -> str:
        return f"{feed}_{window}"

    def _get_cached(self, key: str) -> EarthquakeCollection | None:
        return self._cache.get(key)

    def _build_url(self, feed: str, window: TimeWindow) -> str:
        return f"{USGS_BASE}/{feed}_{window.value}.geojson"

    async def fetch(
        self,
        window: TimeWindow = TimeWindow.DAY,
        min_mag: float = 0.0,
    ) -> EarthquakeCollection:
        """
        Fetch earthquakes for *window*, downloading the smallest USGS feed
        that fully covers *min_mag*.

        For example, min_mag=3.0 fetches the 2.5 feed (floor below 3.0),
        so no Python-side filtering is needed — the feed already excludes
        everything below 2.5, and nothing above 2.5 is missed.
        """
        feed = _feed_for_min_mag(min_mag)
        key = self._cache_key(feed, window)

        if cached := self._get_cached(key):
            logger.debug("Cache hit for %s", key)
            return cached

        url = self._build_url(feed, window)
        logger.info("Fetching USGS feed: %s", url)

        response = await self._client.get(url)
        response.raise_for_status()

        raw = response.json()
        features = [EarthquakeFeature(**f) for f in raw["features"]]
        for feat in features:
            feat.properties.depth = feat.geometry.coordinates[2]

        collection = EarthquakeCollection(
            type=raw["type"],
            features=features,
            count=len(features),
        )
        self._cache.set(key, collection, CACHE_TTL)
        return self._apply_min_mag(collection, min_mag)

    def _apply_min_mag(
        self, collection: EarthquakeCollection, min_mag: float
    ) -> EarthquakeCollection:
        if min_mag <= 0.0:
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
