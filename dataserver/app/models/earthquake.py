"""Earthquake Model file."""

from enum import StrEnum

from pydantic import BaseModel, Field


class TimeWindow(StrEnum):
    """Time Window enum for filtering."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Magnitude(StrEnum):
    """Magnitude Enum."""

    ALL = "all"
    M1 = "1.0"
    M2_5 = "2.5"
    M4_5 = "4.5"
    SIGNIFICANT = "significant"


class EarthquakeProperties(BaseModel):
    """Earthquake Properties."""

    mag: float | None
    place: str | None
    time: int  # epoch ms
    updated: int
    url: str
    detail: str
    felt: int | None
    alert: str | None
    status: str
    tsunami: int
    sig: int
    title: str


class EarthquakeGeometry(BaseModel):
    """Geometry model."""

    type: str
    # Format is [longitude, latitude, depth_km]  # noqa: ERA001
    coordinates: list[float] = Field(..., min_length=3, max_length=3)


class EarthquakeFeature(BaseModel):
    """Earthquake Feature."""

    type: str
    id: str
    properties: EarthquakeProperties
    geometry: EarthquakeGeometry


class EarthquakeCollection(BaseModel):
    """List of collections."""

    type: str
    features: list[EarthquakeFeature]
    count: int
