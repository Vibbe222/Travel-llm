from tools import locations


class FakeCache:
    def __init__(self, value):
        self.value = value
        self.set_calls = []

    def get_json(self, _key):
        return self.value

    def set_json(self, key, value, ttl_seconds=None):
        self.set_calls.append((key, value, ttl_seconds))


def test_location_missing_api_key(monkeypatch):
    monkeypatch.setenv("AMAP_API_KEY", "")
    locations._LOCATION_QUERY_COUNTER.clear()

    result = locations.get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"})

    assert result["success"] is False
    assert result["error"]["message"] == "missing_amap_api_key"
    assert result["error"]["retryable"] is False


def test_location_cache_hit_skips_external_request(monkeypatch):
    cached = {
        "success": True,
        "data": {"source": "amap", "locations": [{"coordinate": "119.296,26.082"}]},
        "error": None,
    }
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(locations, "redis_cache", FakeCache(cached))
    monkeypatch.setattr(
        locations,
        "request_json_with_retry",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("external request should not run")),
    )
    locations._LOCATION_QUERY_COUNTER.clear()

    result = locations.get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"})

    assert result == cached


def test_location_success(monkeypatch):
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    locations._LOCATION_QUERY_COUNTER.clear()

    def fake_request_json_with_retry(**_kwargs):
        return {
            "success": True,
            "data": {
                "status": "1",
                "geocodes": [
                    {
                        "formatted_address": "福建省福州市三坊七巷",
                        "location": "119.296,26.082",
                        "citycode": "0591",
                    }
                ],
            },
            "error": None,
        }

    monkeypatch.setattr(locations, "request_json_with_retry", fake_request_json_with_retry)

    result = locations.get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"})

    assert result["success"] is True
    assert result["data"]["source"] == "amap"
    assert result["data"]["locations"][0]["citycode"] == "0591"


def test_location_business_error(monkeypatch):
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    locations._LOCATION_QUERY_COUNTER.clear()
    monkeypatch.setattr(
        locations,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "0", "info": "INVALID_USER_KEY"}, "error": None},
    )

    result = locations.get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"})

    assert result["success"] is False
    assert result["error"]["message"] == "amap_geocode_failed"
    assert result["error"]["retryable"] is False


def test_location_empty_result(monkeypatch):
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    locations._LOCATION_QUERY_COUNTER.clear()
    monkeypatch.setattr(
        locations,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "1", "geocodes": []}, "error": None},
    )

    result = locations.get_location_coordinate.invoke({"location": "不存在地点", "city": "福州"})

    assert result["success"] is False
    assert result["error"]["message"] == "location_not_found"
    assert result["error"]["retryable"] is False


def test_location_propagates_network_timeout(monkeypatch):
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    locations._LOCATION_QUERY_COUNTER.clear()
    monkeypatch.setattr(
        locations,
        "request_json_with_retry",
        lambda **_kwargs: {
            "success": False,
            "data": None,
            "error": {"message": "http_request_timeout", "detail": "slow", "retryable": True},
        },
    )

    result = locations.get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"})

    assert result["success"] is False
    assert result["error"]["message"] == "http_request_timeout"
    assert result["error"]["retryable"] is True
