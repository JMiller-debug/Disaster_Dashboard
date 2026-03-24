"""Shared TTL cache used across all microservices."""

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class CacheEntry(Generic[T]):
    __slots__ = ("data", "expires_at")

    def __init__(self, data: T, ttl: int) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl


class TTLCache(Generic[T]):
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.data
        return None

    def set(self, key: str, value: T, ttl: int) -> None:
        self._store[key] = CacheEntry(value, ttl)
