import logging
import re
from datetime import UTC, datetime, timedelta
from shared.http import make_client

from app.models import (
    TimeWindow,
    TornadoCollection,
    TornadoFeature,
    TornadoProperties,
    TornadoType,
)
from shared.cache import TTLCache

logger = logging.getLogger(__name__)

SWDI_BASE_URL = "https://www.ncei.noaa.gov/swdiws/json/nx3tvs"
CACHE_TTL = 3600  # 1 hour


class SWDIService:
    def __init__(self) -> None:
        self._client = make_client(timeout=30.0)
        self._cache: TTLCache[TornadoCollection] = TTLCache()

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(self, window: TimeWindow) -> TornadoCollection:
        cache_key = f"swdi_{window}"
        if cached := self._cache.get(cache_key):
            return cached

        # Calculate date range for the API
        end_dt = datetime.now(UTC)
        if window == TimeWindow.WEEK:
            start_dt = end_dt - timedelta(weeks=1)
        else:  # MONTH
            start_dt = end_dt - timedelta(days=30)

        date_str = f"{start_dt.strftime('%Y%m%d')}:{end_dt.strftime('%Y%m%d')}"
        url = f"{SWDI_BASE_URL}/{date_str}"

        logger.info("Fetching SWDI historical data: %s", url)
        print(url)
        resp = await self._client.get(url)
        resp.raise_for_status()

        raw_data = resp.json()
        # print(raw_data)
        features = self._parse_results(raw_data.get("result", []))
        print(features)
        collection = TornadoCollection(
            features=features,
            count=len(features),
            source="swdi",
            window=window,
        )
        self._cache.set(cache_key, collection, CACHE_TTL)
        return collection

    def _parse_results(self, results: list[dict]) -> list[TornadoFeature]:
        parsed = []
        for i, row in enumerate(results):
            print(row["SHAPE"])
            # Convert WKT "POINT (-97 35)" to GeoJSON {"type": "Point", "coordinates": [-97, 35]}
            geometry = self._wkt_to_geojson(row.get("SHAPE", ""))
            print(geometry)
            if not geometry:
                continue
            parsed.append(
                TornadoFeature(
                    type="Feature",
                    id=f"swdi_{row.get('ZTIME')}_{i}",
                    geometry=geometry,
                    properties=TornadoProperties(
                        event="Tornado Vortex Signature",
                        severity=self._calculate_severity(row.get("MAX_SHEAR")),
                        certainty="Radar-Detected",
                        urgency="Immediate",
                        headline=f"Radar Signature detected by {row.get('WSR_ID')}",
                        issued=row.get("ZTIME"),
                        expires=None,
                        status="Historical",
                        type=TornadoType.CONFIRMED,  # Mapping radar signatures to historical records
                        mag=float(row.get("MAX_SHEAR", 0)),
                        state=None,  # SWDI doesn't provide state by default
                    ),
                )
            )
            print(parsed)
        return parsed

    def _wkt_to_geojson(self, wkt: str) -> dict | None:
        """Simple regex to extract coordinates from POINT (lon lat)"""
        match = re.search(r"POINT\s*\(([-\d.]+)\s+([-\d.]+)\)", wkt)
        if match:
            return {
                "type": "Point",
                "coordinates": [float(match.group(1)), float(match.group(2))],
            }
        return None

    def _calculate_severity(self, shear: str | None) -> str:
        try:
            val = float(shear) if shear else 0
            if val > 100:
                return "Extreme"
            if val > 60:
                return "Severe"
            return "Moderate"
        except ValueError:
            return "Unknown"
