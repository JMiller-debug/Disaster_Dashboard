"""Tornado models."""

from enum import StrEnum
from pydantic import BaseModel


class TornadoType(StrEnum):
    WATCH = "watch"
    WARNING = "warning"


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


class TornadoFeature(BaseModel):
    type: str
    id: str
    properties: TornadoProperties
    geometry: dict  # polygon/multipolygon — passed through as-is


class TornadoCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[TornadoFeature]
    count: int
