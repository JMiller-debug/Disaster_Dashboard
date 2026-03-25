"""NASA FIRMS active fire service — worldwide coverage via JSON API."""

import logging
import os
from datetime import UTC, datetime

import httpx
from shared.cache import TTLCache
from shared.http import make_client

from app.models import DayRange, FireCollection, FireFeature, FireProperties, Sensor

logger = logging.getLogger(__name__)

# CSV area API
# Docs: https://firms.modaps.eosdis.nasa.gov/api/area
FIRMS_AREA_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/world/{days}"
)
FIRMS_STATUS_URL = (
    "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={key}"
)

CACHE_TTL = 600  # 10 minutes — FIRMS NRT feeds update every ~3h

# Fallback order when a sensor returns no data.
# Prefer newer/higher-resolution sensors first.
SENSOR_FALLBACK_CHAIN: list[Sensor] = [
    Sensor.VIIRS_NOAA21,
    Sensor.VIIRS_NOAA20,
    Sensor.VIIRS_SNPP,
    Sensor.MODIS,
]


class FIRMSService:
    def __init__(self) -> None:
        self._client = make_client(timeout=30.0)
        self._cache: TTLCache[FireCollection] = TTLCache()
        self._key = os.environ["FIRMS_MAP_KEY"]

    async def close(self) -> None:
        await self._client.aclose()

    async def check_quota(self) -> dict:
        """Return current transaction usage from the MAP_KEY status endpoint."""
        url = FIRMS_STATUS_URL.format(key=self._key)
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def fetch(
        self,
        sensor: Sensor | None = None,
        days: DayRange = DayRange.ONE,
    ) -> FireCollection:
        if sensor is None:
            return await self._fetch_all(days)

        # Build a deduplicated fallback list: requested sensor first, then the
        # rest of the chain in order, skipping any already-tried sensors.
        chain = [sensor] + [s for s in SENSOR_FALLBACK_CHAIN if s != sensor]

        for candidate in chain:
            cache_key = f"{candidate}_{days}"
            if cached := self._cache.get(cache_key):
                logger.debug("Cache hit for %s", cache_key)
                return cached

            url = FIRMS_AREA_URL.format(
                key=self._key,
                sensor=candidate.value,
                days=days.value,
            )
            logger.info("Fetching FIRMS feed: %s", url)

            try:
                resp = await self._client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("FIRMS request failed for %s: %s", candidate, exc)
                continue

            features = _parse_csv(candidate, resp.text)

            if not features:
                logger.warning(
                    "Sensor %s returned no data for days=%s, trying next in chain",
                    candidate.value,
                    days.value,
                )
                continue

            if candidate != sensor:
                logger.info(
                    "Fell back from %s to %s (days=%s)",
                    sensor.value,
                    candidate.value,
                    days.value,
                )

            collection = FireCollection(
                features=features,
                count=len(features),
                sensor=candidate,
                days=days,
            )
            self._cache.set(cache_key, collection, CACHE_TTL)
            return collection

        raise RuntimeError(
            f"All FIRMS sensors exhausted for days={days.value} — no data available"
        )

    async def _fetch_all(self, days: DayRange) -> FireCollection:
        """Fetch from every sensor and merge into a single collection."""
        import asyncio

        results = await asyncio.gather(
            *[self._fetch_one(s, days) for s in SENSOR_FALLBACK_CHAIN],
            return_exceptions=True,
        )

        seen: set[tuple[float, float, str | None]] = set()
        merged: list[FireFeature] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(
                    "Sensor fetch failed during all-sensor merge: %s", result
                )
                continue
            for feature in result.features:
                coords = feature.geometry.get("coordinates", [])
                key = (coords[0], coords[1], feature.properties.acquired)
                if key not in seen:
                    seen.add(key)
                    merged.append(feature)

        # Re-ID features now that they're merged across sensors
        for i, f in enumerate(merged):
            f.id = f"merged_{i}"

        return FireCollection(
            features=merged,
            count=len(merged),
            sensor=Sensor.VIIRS_SNPP,  # nominal; reflects no single sensor
            days=days,
        )

    async def _fetch_one(self, sensor: Sensor, days: DayRange) -> FireCollection:
        """Fetch a single sensor with no fallback logic (used during all-sensor merge)."""
        cache_key = f"{sensor}_{days}"
        if cached := self._cache.get(cache_key):
            return cached

        url = FIRMS_AREA_URL.format(key=self._key, sensor=sensor.value, days=days.value)
        logger.info("Fetching FIRMS feed: %s", url)
        resp = await self._client.get(url)
        resp.raise_for_status()

        features = _parse_csv(sensor, resp.text)
        collection = FireCollection(
            features=features, count=len(features), sensor=sensor, days=days
        )
        self._cache.set(cache_key, collection, CACHE_TTL)
        return collection


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _parse_csv(sensor: Sensor, text: str) -> list[FireFeature]:
    """Parse FIRMS CSV response into FireFeatures.

    VIIRS columns:  latitude, longitude, bright_ti4, scan, track, acq_date,
                    acq_time, satellite, instrument, confidence, version,
                    bright_ti5, frp, daynight
    MODIS columns:  latitude, longitude, brightness, scan, track, acq_date,
                    acq_time, satellite, instrument, confidence, version,
                    bright_t31, frp, daynight
    """
    import csv, io

    features: list[FireFeature] = []
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, ValueError):
            continue
        brightness = _float(row.get("bright_ti4") or row.get("brightness"))
        frp = _float(row.get("frp"))
        acquired = _parse_acquired(row.get("acq_date"), row.get("acq_time"))
        features.append(
            FireFeature(
                id=f"{sensor.value}_{i}",
                geometry={"type": "Point", "coordinates": [lon, lat]},
                properties=FireProperties(
                    brightness=brightness,
                    frp=frp,
                    confidence=row.get("confidence"),
                    acquired=acquired,
                    sensor=row.get("instrument"),
                    satellite=row.get("satellite"),
                    day_night=row.get("daynight"),
                ),
            )
        )
    return features


def _parse_acquired(acq_date: str | None, acq_time: str | None) -> str | None:
    """
    Build an ISO-8601 UTC datetime string from FIRMS date + time fields.

    acq_date: "2025-06-06"
    acq_time: "142" or "0142" (HHMM, zero-padded or not, always UTC)
    """
    if not acq_date or acq_time is None:
        return None
    try:
        time_str = str(acq_time).zfill(4)  # ensure 4 digits
        dt = datetime(
            year=int(acq_date[:4]),
            month=int(acq_date[5:7]),
            day=int(acq_date[8:10]),
            hour=int(time_str[:2]),
            minute=int(time_str[2:]),
            tzinfo=UTC,
        )
        return dt.isoformat()
    except (ValueError, IndexError):
        return None


def _float(val: object) -> float | None:
    try:
        return float(val) if val is not None else None  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
