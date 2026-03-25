"""Cyclone/hurricane/typhoon models."""

from pydantic import BaseModel


class StormProperties(BaseModel):
    """Base properties of the storm."""

    name: str | None
    basin: str | None  # e.g. "Atlantic", "Eastern Pacific"
    classification: str | None  # TD, TS, HU, TY etc.
    intensity: int | None  # max sustained wind knots
    pressure: int | None  # central pressure hPa
    timestamp: str | None
    source: str | None  # NHC, JTWC etc.


class StormFeature(BaseModel):
    """Top level storm details."""

    type: str
    id: str
    properties: StormProperties
    geometry: dict  # Point for current position


class ForecastTrack(BaseModel):
    """Cone of uncertainty / forecast track for a single storm."""

    storm_id: str
    storm_name: str | None
    track: dict  # LineString GeoJSON
    cone: dict | None  # Polygon GeoJSON uncertainty cone


class CycloneCollection(BaseModel):
    """Collection of StormFeatures."""

    type: str = "FeatureCollection"
    features: list[StormFeature]
    tracks: list[ForecastTrack] = []
    count: int
