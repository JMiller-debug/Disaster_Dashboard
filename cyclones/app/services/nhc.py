"""
NOAA NHC + GDACS cyclone service (global coverage).

Basins covered:
  NHC   — Atlantic (AL), Eastern Pacific (EP), Central Pacific (CP)
  GDACS — Western Pacific, Indian Ocean, Southern Hemisphere, and any basin
           NHC doesn't cover; deduplicates against NHC by proximity.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field

import httpx
from defusedxml import ElementTree
from shared.cache import TTLCache
from shared.http import make_client

from app.models import CycloneCollection, ForecastTrack, StormFeature, StormProperties

logger = logging.getLogger(__name__)

# ── NHC ───────────────────────────────────────────────────────────────────────
NHC_ACTIVE = "https://www.nhc.noaa.gov/CurrentStorms.json"
NHC_TRACK_URL = (
    "https://www.nhc.noaa.gov/storm_graphics/api/{storm_id}_best_track.geojson"
)
NHC_CONE_URL = "https://www.nhc.noaa.gov/storm_graphics/api/{storm_id}_5day_pgn.geojson"

# ── GDACS ─────────────────────────────────────────────────────────────────────
# GDACS RSS feed — covers all active tropical cyclones worldwide
# Docs: https://www.gdacs.org/xml.aspx
GDACS_RSS = "https://gdacs.org/xml/rss_tc_7d.xml"

# Deduplicate GDACS storms that are already in NHC data.
# If a GDACS storm centre is within this many degrees of an NHC storm, skip it.
_DEDUP_DEGREES = 5.0

CACHE_TTL = 360  # 6 minutes

TITLE_MAP = [
    ("SUPER TYPHOON", "STY"),
    ("TYPHOON", "TY"),
    ("TROPICAL STORM", "TS"),
    ("TROPICAL DEPRESSION", "TD"),
    ("CYCLONE", "TC"),
]

HURRICANE_TIERS = [
    (137, "HU5"),
    (113, "HU4"),
    (96, "HU3"),
]

ALERT_MAP = {"GREEN": "TD", "ORANGE": "TS", "RED": "TY"}


@dataclass(frozen=True)
class Basin:
    """Basin Class to identify Cyclone locations."""

    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def contains(self, lat: float, lon: float) -> bool:
        """Check if the basin contains the cyclone."""
        return (
            self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max
        )


BASINS: list[Basin] = [
    Basin("Western Pacific", lat_min=0, lat_max=90, lon_min=100, lon_max=180),
    Basin("Indian Ocean", lat_min=0, lat_max=90, lon_min=40, lon_max=100),
    Basin("Southern Indian Ocean", lat_min=-90, lat_max=0, lon_min=20, lon_max=135),
    Basin("Australian Region", lat_min=-90, lat_max=0, lon_min=135, lon_max=180),
    Basin("South Atlantic", lat_min=-90, lat_max=0, lon_min=-180, lon_max=20),
    Basin("Eastern Pacific", lat_min=-90, lat_max=90, lon_min=-180, lon_max=-80),
]

_FALLBACK = "Atlantic"


@dataclass
class _RawStorm:
    """RawStorm data properties."""

    storm_id: str
    name: str | None
    basin: str
    classification: str | None
    intensity: int | None  # max sustained wind, knots
    pressure: int | None  # central pressure, hPa
    lat: float
    lon: float
    timestamp: str | None
    source: str
    extra: dict = field(default_factory=dict)


class NHCService:
    """American National Hurricane Centre service."""

    def __init__(self) -> None:
        """Class Init."""
        self._client = make_client(timeout=10.0)
        self._cache: TTLCache[CycloneCollection] = TTLCache()

    async def close(self) -> None:
        """Close connection to NHC."""
        await self._client.aclose()

    async def fetch(self) -> CycloneCollection:
        """Fetch data."""
        if cached := self._cache.get("cyclones"):
            return cached

        nhc_result, gdacs_result = await asyncio.gather(
            self._fetch_nhc(),
            self._fetch_gdacs(),
            return_exceptions=True,
        )

        nhc_storms: list[_RawStorm] = nhc_result if isinstance(nhc_result, list) else []
        if isinstance(nhc_result, Exception):
            logger.error("NHC fetch failed: %s", nhc_result)

        gdacs_storms: list[_RawStorm] = []
        if isinstance(gdacs_result, list):
            gdacs_storms = _deduplicate(gdacs_result, nhc_storms)
        else:
            logger.error("GDACS fetch failed: %s", gdacs_result)

        all_storms = nhc_storms + gdacs_storms
        features = [_raw_to_feature(s) for s in all_storms]

        # Fetch NHC forecast tracks (GDACS doesn't publish GeoJSON tracks)
        track_results = await asyncio.gather(
            *[_fetch_nhc_track(self._client, s.storm_id) for s in nhc_storms],
            return_exceptions=True,
        )
        tracks = [t for t in track_results if isinstance(t, ForecastTrack)]

        collection = CycloneCollection(
            features=features,
            tracks=tracks,
            count=len(features),
        )
        self._cache.set("cyclones", collection, CACHE_TTL)
        return collection

    # ── NHC ───────────────────────────────────────────────────────────────────

    async def _fetch_nhc(self) -> list[_RawStorm]:
        resp = await self._client.get(NHC_ACTIVE)
        resp.raise_for_status()
        storms: list[_RawStorm] = []
        for s in resp.json().get("activeStorms", []):
            lat = s.get("latitudeNumeric")
            lon = s.get("longitudeNumeric")
            if lat is None or lon is None:
                continue
            storms.append(
                _RawStorm(
                    storm_id=s.get("id", ""),
                    name=s.get("name"),
                    basin=s.get("basin", "Atlantic"),
                    classification=s.get("classification"),
                    intensity=s.get("intensity"),
                    pressure=s.get("pressure"),
                    lat=lat,
                    lon=lon,
                    timestamp=s.get("dateTime"),
                    source="NHC",
                )
            )
        logger.info("NHC: %d active storms", len(storms))
        return storms

    # ── GDACS ─────────────────────────────────────────────────────────────────

    async def _fetch_gdacs(self) -> list[_RawStorm]:
        resp = await self._client.get(GDACS_RSS)
        resp.raise_for_status()
        storms = _parse_gdacs_rss(resp.text)
        logger.info("GDACS: %d tropical cyclones", len(storms))
        return storms


# ── GDACS RSS parser ──────────────────────────────────────────────────────────

# GDACS uses a custom namespace for its extended fields
_GDACS_NS = {
    "gdacs": "http://www.gdacs.org",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _parse_gdacs_rss(xml_text: str) -> list[_RawStorm]:
    storms: list[_RawStorm] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        logger.exception("GDACS RSS parse error: %s")
        return storms

    for item in root.iter("item"):
        # GDACS only — filter to tropical cyclones
        event_type = _xt(item, "gdacs:eventtype", _GDACS_NS)
        if event_type and event_type.upper() != "TC":
            continue

        title = _xt(item, "title") or ""
        pub = _xt(item, "pubDate")
        # gdacs:eventname e.g. "MAWAR", fallback to parsing title
        name = _xt(item, "gdacs:eventname", _GDACS_NS)
        if not name and title:
            # title format: "Tropical Cyclone MAWAR" or "Typhoon MAWAR-23"
            parts = title.split()
            if parts:
                candidate = parts[-1].split("-")[0]
                if candidate.isupper():
                    name = candidate.title()

        storm_id = _xt(item, "gdacs:eventid", _GDACS_NS) or ""

        geo_point = item.find("geo:Point", _GDACS_NS)
        lat = _float_or_none(_xt(geo_point, "geo:lat", _GDACS_NS))
        lon = _float_or_none(_xt(geo_point, "geo:long", _GDACS_NS))
        if lat is None or lon is None:
            continue

        # Wind speed in knots (gdacs:severity or description)
        severity_val = _xt(item, "gdacs:severity", _GDACS_NS)
        intensity = _parse_gdacs_wind(severity_val or "")

        # Alert level → rough classification
        alert = (_xt(item, "gdacs:alertlevel", _GDACS_NS) or "").upper()
        classification = _gdacs_alert_to_class(title, alert, intensity)

        basin = _infer_basin(lat, lon)

        storms.append(
            _RawStorm(
                storm_id=f"GDACS-{storm_id}",
                name=name,
                basin=basin,
                classification=classification,
                intensity=intensity,
                pressure=None,  # GDACS RSS doesn't publish central pressure
                lat=lat,
                lon=lon,
                timestamp=pub,
                source="GDACS",
            )
        )

    return storms


def _parse_gdacs_wind(text: str) -> int | None:
    """Extract wind speed from GDACS severity string, e.g. '55 kt maximum winds'."""
    m = re.search(r"(\d+)\s*kt", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Sometimes given in km/h
    m = re.search(r"(\d+)\s*km/?h", text, re.IGNORECASE)
    if m:
        return int(int(m.group(1)) / 1.852)  # convert to knots
    return None


def _gdacs_alert_to_class(title: str, alert: str, wind_kt: int | None) -> str:
    """Map GDACS alert level + title keywords to a short classification code."""
    t = title.upper()

    if "HURRICANE" in t:
        return next(
            (
                code
                for threshold, code in HURRICANE_TIERS
                if wind_kt and wind_kt >= threshold
            ),
            "HU",
        )

    keyword_match = next((code for keyword, code in TITLE_MAP if keyword in t), None)
    return keyword_match or ALERT_MAP.get(alert, "TC")


def _infer_basin(lat: float, lon: float) -> str:
    return next((b.name for b in BASINS if b.contains(lat, lon)), _FALLBACK)


def _deduplicate(gdacs: list[_RawStorm], nhc: list[_RawStorm]) -> list[_RawStorm]:
    """Drop GDACS storms that are within _DEDUP_DEGREES of an NHC storm."""
    out: list[_RawStorm] = []
    for gs in gdacs:
        close = any(
            abs(gs.lat - ns.lat) < _DEDUP_DEGREES
            and abs(gs.lon - ns.lon) < _DEDUP_DEGREES
            for ns in nhc
        )
        if not close:
            out.append(gs)
    return out


# ── Shared helpers ────────────────────────────────────────────────────────────


def _raw_to_feature(s: _RawStorm) -> StormFeature:
    return StormFeature(
        type="Feature",
        id=s.storm_id,
        geometry={"type": "Point", "coordinates": [s.lon, s.lat]},
        properties=StormProperties(
            name=s.name,
            basin=s.basin,
            classification=s.classification,
            intensity=s.intensity,
            pressure=s.pressure,
            timestamp=s.timestamp,
            source=s.source,
        ),
    )


async def _fetch_nhc_track(
    client: httpx.AsyncClient, storm_id: str
) -> ForecastTrack | None:
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
            storm_name=None,
            track=track_geojson,
            cone=cone_geojson,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch NHC track for %s", storm_id)
        return None


def _xt(el: ElementTree.Element, tag: str, ns: dict | None = None) -> str | None:
    child = el.find(tag, ns or {})
    return child.text.strip() if child is not None and child.text else None


def _float_or_none(val: str | None) -> float | None:
    try:
        return float(val) if val else None
    except ValueError:
        return None
