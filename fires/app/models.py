"""Fire hotspot models."""

from enum import StrEnum
from pydantic import BaseModel


class DayRange(StrEnum):
    ONE = "1"
    TWO = "2"
    THREE = "3"
    SEVEN = "7"


class Sensor(StrEnum):
    VIIRS_SNPP = "VIIRS_SNPP_NRT"
    VIIRS_NOAA20 = "VIIRS_NOAA20_NRT"
    MODIS = "MODIS_NRT"


class FireProperties(BaseModel):
    brightness: float | None  # brightness temperature (K)
    frp: float | None  # fire radiative power (MW)
    confidence: str | None  # low / nominal / high (VIIRS) or 0-100 (MODIS)
    acquired: str | None  # ISO datetime
    sensor: str | None
    satellite: str | None
    day_night: str | None  # D or N


class FireFeature(BaseModel):
    type: str = "Feature"
    id: str
    properties: FireProperties
    geometry: dict  # Point


class FireCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[FireFeature]
    count: int
    sensor: Sensor
    days: DayRange
