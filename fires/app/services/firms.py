"""NASA FIRMS active fire service — worldwide coverage."""

import csv
import io
import logging
import os

from shared.http import make_client


from app.models import DayRange, FireCollection, FireFeature, FireProperties, Sensor
from shared.cache import TTLCache

logger = logging.getLogger(__name__)

# FIRMS CSV API — returns one row per hotspot detection
# Docs: https://firms.modaps.eosdis.nasa.gov/api/area/
FIRMS_BASE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/world/{days}"
)

CACHE_TTL = 600  # 10 minutes — FIRMS updates ~every 3h for NRT feeds


class FIRMSService:
    def __init__(self) -> None:
        self._client = make_client(timeout=30.0)
        self._cache: TTLCache[FireCollection] = TTLCache()
        self._key = os.environ["FIRMS_MAP_KEY"]

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(
        self,
        sensor: Sensor = Sensor.VIIRS_SNPP,
        days: DayRange = DayRange.ONE,
    ) -> FireCollection:
        cache_key = f"{sensor}_{days}"
        if cached := self._cache.get(cache_key):
            return cached

        url = FIRMS_BASE.format(key=self._key, sensor=sensor.value, days=days.value)
        logger.info("Fetching FIRMS feed: %s", url)

        resp = await self._client.get(url)
        resp.raise_for_status()

        features = _parse_csv(resp.text, sensor)
        collection = FireCollection(
            features=features,
            count=len(features),
            sensor=sensor,
            days=days,
        )
        self._cache.set(cache_key, collection, CACHE_TTL)
        return collection


def _parse_csv(text: str, sensor: Sensor) -> list[FireFeature]:
    """Parse FIRMS CSV into GeoJSON-style features.

    VIIRS columns:  latitude, longitude, bright_ti4, scan, track, acq_date,
                    acq_time, satellite, instrument, confidence, version,
                    bright_ti5, frp, daynight
    MODIS columns:  latitude, longitude, brightness, scan, track, acq_date,
                    acq_time, satellite, instrument, confidence, version,
                    bright_t31, frp, daynight
    """
    features: list[FireFeature] = []
    reader = csv.DictReader(io.StringIO(text))

    for i, row in enumerate(reader):
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, ValueError):
            continue

        # brightness column differs between VIIRS and MODIS
        brightness_raw = row.get("bright_ti4") or row.get("brightness")
        try:
            brightness = float(brightness_raw) if brightness_raw else None
        except ValueError:
            brightness = None

        try:
            frp = float(row["frp"]) if row.get("frp") else None
        except ValueError:
            frp = None

        acq_date = row.get("acq_date", "")
        acq_time = row.get("acq_time", "")
        acquired = (
            f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}Z"
            if acq_date and acq_time
            else None
        )

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
