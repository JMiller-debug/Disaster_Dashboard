"""NOAA NHC + IBTrACS cyclone service (global coverage)."""

import asyncio
import logging

import httpx
from shared.cache import TTLCache

from app.models import CycloneCollection, ForecastTrack, StormFeature, StormProperties

logger = logging.getLogger(__name__)

# NHC active storm GeoJSON feeds (Atlantic + E/C Pacific)
NHC_BASE = "https://www.nhc.noaa.gov/CurrentStorms.json"

# NHC GeoJSON track/cone per storm — requires storm ID e.g. "AL012024"
NHC_TRACK_URL = (
    "https://www.nhc.noaa.gov/storm_graphics/api/{storm_id}_best_track.geojson"
)
NHC_CONE_URL = "https://www.nhc.noaa.gov/storm_graphics/api/{storm_id}_5day_pgn.geojson"

CACHE_TTL = 360  # 6 minutes — NHC updates every 6h (3h when near shore)


class NHCService:
    """NHC Service for cyclones."""

    def __init__(self) -> None:
        """Init class."""
        self._client = httpx.AsyncClient(timeout=15.0)
        self._cache: TTLCache[CycloneCollection] = TTLCache()

    async def close(self) -> None:
        """Close connection."""
        await self._client.aclose()

    async def fetch(self) -> CycloneCollection:
        """Fetch CycloneCollection."""
        if cached := self._cache.get("cyclones"):
            return cached

        resp = await self._client.get(NHC_BASE)
        resp.raise_for_status()
        raw = resp.json()

        active_storms = raw.get("activeStorms", [])
        features: list[StormFeature] = []
        track_tasks = []

        for storm in active_storms:
            feat = _parse_storm(storm)
            if feat:
                features.append(feat)
                track_tasks.append(_fetch_track(self._client, storm))

        tracks = await asyncio.gather(*track_tasks, return_exceptions=True)
        valid_tracks = [t for t in tracks if isinstance(t, ForecastTrack)]

        collection = CycloneCollection(
            features=features,
            tracks=valid_tracks,
            count=len(features),
        )
        self._cache.set("cyclones", collection, CACHE_TTL)
        return collection


def _parse_storm(raw: dict) -> StormFeature | None:
    """Parse raw response and return StormFeature."""
    lat = raw.get("latitudeNumeric")
    lon = raw.get("longitudeNumeric")
    if lat is None or lon is None:
        return None

    return StormFeature(
        type="Feature",
        id=raw.get("id", ""),
        geometry={"type": "Point", "coordinates": [lon, lat]},
        properties=StormProperties(
            name=raw.get("name"),
            basin=raw.get("basin"),
            classification=raw.get("classification"),
            intensity=raw.get("intensity"),
            pressure=raw.get("pressure"),
            timestamp=raw.get("dateTime"),
            source="NHC",
        ),
    )


async def _fetch_track(client: httpx.AsyncClient, storm: dict) -> ForecastTrack | None:
    """Fetch the track of a specific cyclone."""
    storm_id = storm.get("id", "")
    if not storm_id:
        return None
    try:
        track_resp, cone_resp = await asyncio.gather(
            client.get(NHC_TRACK_URL.format(storm_id=storm_id)),
            client.get(NHC_CONE_URL.format(storm_id=storm_id)),
            return_exceptions=True,
        )
        track_geojson = (
            track_resp.json() if not isinstance(track_resp, Exception) else None
        )
        cone_geojson = (
            cone_resp.json() if not isinstance(cone_resp, Exception) else None
        )

        if not track_geojson:
            return None

        return ForecastTrack(
            storm_id=storm_id,
            storm_name=storm.get("name"),
            track=track_geojson,
            cone=cone_geojson,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch track for storm %s", storm_id)
        return None
