"""Tornado models."""

from enum import StrEnum

from pydantic import BaseModel


class TornadoType(StrEnum):
    WATCH = "watch"
    WARNING = "warning"
    CONFIRMED = "confirmed"  # historical SPC record


class TimeWindow(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class TornadoProperties(BaseModel):
    event: str | None
    severity: str | None
    certainty: str | None
    urgency: str | None
    headline: str | None
    issued: str | None
    expires: str | None
    status: str | None
    type: TornadoType
    # SPC-only fields
    mag: float | None = None  # EF scale
    injuries: int | None = None
    fatalities: int | None = None
    state: str | None = None
    length_mi: float | None = None
    width_yd: float | None = None


class TornadoFeature(BaseModel):
    type: str
    id: str
    properties: TornadoProperties
    geometry: dict  # Point (NWS) or LineString (SPC)


class TornadoCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[TornadoFeature]
    count: int
    source: str = "nws"  # "nws" | "spc"
    window: TimeWindow = TimeWindow.DAY
