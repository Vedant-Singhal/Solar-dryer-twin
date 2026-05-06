"""Redis prediction cache. Keys are rounded inputs; values are JSON tray temps in K."""
from __future__ import annotations
import json
from typing import Optional

import redis

from app.config import settings


class PredictionCache:
    def __init__(self, url: str, ttl: int, decimals: int) -> None:
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl
        self._decimals = decimals

    def _key(self, hf: float, porosity: float) -> str:
        return f"pred:{settings.model_version}:{round(hf, self._decimals)}:{round(porosity, self._decimals)}"

    def get(self, hf: float, porosity: float) -> Optional[tuple[float, float, float, float]]:
        try:
            raw = self._client.get(self._key(hf, porosity))
        except redis.RedisError:
            return None
        if raw is None:
            return None
        t = json.loads(raw)
        return (t[0], t[1], t[2], t[3])

    def set(self, hf: float, porosity: float, temps_k: tuple[float, float, float, float]) -> None:
        try:
            self._client.set(self._key(hf, porosity), json.dumps(list(temps_k)), ex=self._ttl)
        except redis.RedisError:
            pass  # cache is best-effort

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False


_cache: PredictionCache | None = None


def get_cache() -> PredictionCache:
    global _cache
    if _cache is None:
        _cache = PredictionCache(settings.redis_url, settings.cache_ttl_seconds, settings.cache_round_decimals)
    return _cache
