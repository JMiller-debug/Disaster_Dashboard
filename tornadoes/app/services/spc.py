"""SPC historical tornado service."""

import csv
import io
import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.models import (
    TornadoCollection,
    TornadoFeature,
    TornadoProperties,
    TornadoType,
    TimeWindow,
)
from shared.cache import TTLCache

logger = logging.getLogger(__name__)

SPC_BASE = "https://www.spc.noaa.gov/climo/torn/torn{year}.csv"
CACHE_TTL = 3600  # historical data doesn't change, cache for 1h


class SPCService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: TTLCache[list[TornadoFeature]] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(self, window: TimeWindow) -> TornadoCollection:
        since = _window_to_datetime(window)
        # Gather years we need to cover — usually just current year,
        # but "month" in early January would need previous year too
        years_needed = _years_needed(since)

        features: list[TornadoFeature] = []
        for year in years_needed:
            year_features = await self._fetch_year(year)
            features.extend(year_features)

        # Filter to the requested window
        cutoff_ts = since.timestamp() * 1000  # epoch ms to match NWS convention
        filtered = [f for f in features if _feature_time(f) >= cutoff_ts]
        filtered.sort(key=_feature_time, reverse=True)

        return TornadoCollection(
            features=filtered,
            count=len(filtered),
            source="spc",
            window=window,
        )

    async def _fetch_year(self, year: int) -> list[TornadoFeature]:
        cache_key = f"spc_{year}"
        if cached := self._cache.get(cache_key):
            logger.debug("Cache hit for SPC year %d", year)
            return cached

        url = SPC_BASE.format(year=year)
        logger.info("Fetching SPC CSV: %s", url)
        resp = await self._client.get(url)
        resp.raise_for_status()

        features = _parse_csv(resp.text, year)
        self._cache.set(cache_key, features, CACHE_TTL)
        logger.info("Parsed %d tornado records for %d", len(features), year)
        return features


def _window_to_datetime(window: TimeWindow) -> datetime:
    now = datetime.now(UTC)
    match window:
        case TimeWindow.WEEK:
            return now - timedelta(weeks=1)
        case TimeWindow.MONTH:
            return now - timedelta(days=30)
        case _:
            # Shouldn't reach here — hour/day use NWS — but be safe
            return now - timedelta(days=1)


def _years_needed(since: datetime) -> list[int]:
    now = datetime.now(UTC)
    years = set()
    year = since.year
    while year <= now.year:
        years.add(year)
        year += 1
    return sorted(years)


def _feature_time(f: TornadoFeature) -> float:
    """Return epoch ms from the issued field for sorting/filtering."""
    if f.properties.issued is None:
        return 0.0
    try:
        dt = datetime.fromisoformat(f.properties.issued)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp() * 1000
    except ValueError:
        return 0.0


def _parse_csv(text: str, year: int) -> list[TornadoFeature]:
    features: list[TornadoFeature] = []
    reader = csv.DictReader(io.StringIO(text))

    for i, row in enumerate(reader):
        try:
            slat = float(row["slat"])
            slon = float(row["slon"])
            elat = float(row.get("elat") or 0)
            elon = float(row.get("elon") or 0)
        except (KeyError, ValueError):
            continue

        # Build a LineString if we have a real end point, otherwise a Point
        has_track = elat != 0.0 and elon != 0.0 and (elat != slat or elon != slon)
        if has_track:
            geometry: dict = {
                "type": "LineString",
                "coordinates": [[slon, slat], [elon, elat]],
            }
        else:
            geometry = {"type": "Point", "coordinates": [slon, slat]}

        # Parse date — SPC format is yr/mo/dy + time (HHMM) + tz offset
        try:
            mo = row["mo"].zfill(2)
            dy = row["dy"].zfill(2)
            time_str = row.get("time", "0000").zfill(4)
            tz_offset = int(row.get("tz", "0") or 0)
            issued = (
                f"{year}-{mo}-{dy}T"
                f"{time_str[:2]}:{time_str[2:]}:00"
                f"{_tz_offset_str(tz_offset)}"
            )
        except (KeyError, ValueError):
            issued = f"{year}-01-01T00:00:00+00:00"

        try:
            mag = float(row.get("mag") or -1)
        except ValueError:
            mag = None

        features.append(
            TornadoFeature(
                type="Feature",
                id=f"spc_{year}_{i}",
                geometry=geometry,
                properties=TornadoProperties(
                    event="Tornado",
                    severity=_ef_to_severity(mag),
                    certainty="Observed",
                    urgency=None,
                    headline=f"EF{int(mag) if mag is not None and mag >= 0 else '?'} tornado in {row.get('st', '?')}",
                    issued=issued,
                    expires=None,
                    status="Confirmed",
                    type=TornadoType.CONFIRMED,
                    mag=mag if mag is not None and mag >= 0 else None,
                    injuries=_int_or_none(row.get("inj")),
                    fatalities=_int_or_none(row.get("fat")),
                    state=row.get("st"),
                    length_mi=_float_or_none(row.get("len")),
                    width_yd=_float_or_none(row.get("wid")),
                ),
            )
        )

    return features


def _ef_to_severity(mag: float | None) -> str:
    if mag is None or mag < 0:
        return "Unknown"
    if mag >= 4:
        return "Extreme"
    if mag >= 3:
        return "Severe"
    if mag >= 2:
        return "Moderate"
    return "Minor"


def _tz_offset_str(tz: int) -> str:
    """Convert SPC tz integer (hours behind UTC) to ISO offset string."""
    offset = -tz
    sign = "+" if offset >= 0 else "-"
    return f"{sign}{abs(offset):02d}:00"


def _int_or_none(val: str | None) -> int | None:
    try:
        return int(val) if val else None
    except ValueError:
        return None


def _float_or_none(val: str | None) -> float | None:
    try:
        return float(val) if val else None
    except ValueError:
        return None
