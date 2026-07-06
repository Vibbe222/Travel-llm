import hashlib
import json
import logging
from typing import Any

from settings import get_settings


logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def make_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    settings = get_settings()
    normalized = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{settings.redis_key_prefix}:cache:{namespace}:{digest}"


class RedisCacheService:
    def __init__(self) -> None:
        self._client = None
        self._ready = False

    def reset(self) -> None:
        self._client = None
        self._ready = False

    def _get_client(self):
        settings = get_settings()
        if not settings.cache_enabled:
            return None
        if self._ready:
            return self._client
        self._ready = True
        try:
            import redis
        except ImportError:
            logger.warning("redis package is not installed, cache disabled")
            self._client = None
            return None
        try:
            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
        except Exception as exc:
            logger.warning("redis unavailable, cache disabled: %s", exc)
            self._client = None
        return self._client

    def ping(self) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.ping()
            return True
        except Exception:
            return False

    def get_json(self, key: str) -> Any | None:
        client = self._get_client()
        if not client:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("redis get failed for key=%s: %s", key, exc)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        client = self._get_client()
        if not client:
            return
        ttl = ttl_seconds or get_settings().cache_ttl_seconds
        try:
            client.setex(key, ttl, json.dumps(_json_safe(value), ensure_ascii=False))
        except Exception as exc:
            logger.warning("redis set failed for key=%s: %s", key, exc)


redis_cache = RedisCacheService()
