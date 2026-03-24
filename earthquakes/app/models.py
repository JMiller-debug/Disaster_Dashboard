"""Earthquake models."""

from enum import StrEnum
from pydantic import BaseModel, Field


class TimeWindow(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Magnitude(StrEnum):
    ALL = "all"
    M1 = "1.0"
    M2_5 = "2.5"
    M4_5 = "4.5"
    SIGNIFICANT = "significant"


class EarthquakeProperties(BaseModel):
    mag: float | None
    place: str | None
    time: int
    updated: int
    url: str
    detail: str
    felt: int | None
    alert: str | None
    status: str
    tsunami: int
    sig: int
    title: str
    depth: float | None = None


class EarthquakeGeometry(BaseModel):
    type: str
    coordinates: list[float] = Field(..., min_length=3, max_length=3)


class EarthquakeFeature(BaseModel):
    type: str
    id: str
    properties: EarthquakeProperties
    geometry: EarthquakeGeometry


class EarthquakeCollection(BaseModel):
    type: str
    features: list[EarthquakeFeature]
    count: int
