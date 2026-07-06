import pytest
from uuid import uuid4

from settings import get_settings
from utils.redis_cache import redis_cache


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    monkeypatch.setenv("REDIS_KEY_PREFIX", f"test_travel_llm_{uuid4().hex}")
    get_settings.cache_clear()
    redis_cache.reset()
    yield
    redis_cache.reset()
    get_settings.cache_clear()
