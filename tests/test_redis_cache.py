from utils.redis_cache import RedisCacheService, make_cache_key


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def ping(self):
        return True

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl


def test_make_cache_key_is_stable_for_dict_order(monkeypatch):
    monkeypatch.setenv("REDIS_KEY_PREFIX", "test")

    first = make_cache_key("location", {"city": "福州", "location": "三坊七巷"})
    second = make_cache_key("location", {"location": "三坊七巷", "city": "福州"})

    assert first == second
    assert first.startswith("test:cache:location:")


def test_redis_cache_service_degrades_when_redis_package_missing(monkeypatch):
    service = RedisCacheService()

    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    assert service.get_json("key") is None
    assert service.ping() is False


def test_redis_cache_service_reads_and_writes_json():
    fake = FakeRedis()
    service = RedisCacheService()
    service._client = fake
    service._ready = True

    service.set_json("k", {"城市": "福州"}, ttl_seconds=30)

    assert service.get_json("k") == {"城市": "福州"}
    assert fake.ttls["k"] == 30
