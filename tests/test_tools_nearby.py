from tools import nearby


def test_nearby_invalid_query_returns_fail():
    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "invalid_poi_query"
    assert result["error"]["retryable"] is False


def test_nearby_success(monkeypatch):
    monkeypatch.setattr(nearby, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")

    def fake_request_json_with_retry(**_kwargs):
        return {
            "success": True,
            "data": {
                "status": "1",
                "count": "1",
                "pois": [
                    {
                        "name": "测试餐厅",
                        "type": "中餐厅",
                        "address": "测试路1号",
                        "distance": "120",
                        "location": "113.1,29.3",
                        "biz_ext": {"rating": "4.5", "cost": "50"},
                    }
                ],
            },
            "error": None,
        }

    monkeypatch.setattr(nearby, "request_json_with_retry", fake_request_json_with_retry)

    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "中餐厅",
    })

    assert result["success"] is True
    assert result["data"]["pois"][0]["name"] == "测试餐厅"


def test_nearby_empty_result(monkeypatch):
    monkeypatch.setattr(nearby, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        nearby,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "1", "pois": []}, "error": None},
    )

    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "中餐厅",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "nearby_poi_empty"


def test_nearby_missing_api_key(monkeypatch):
    monkeypatch.setattr(nearby, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)

    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "中餐厅",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "missing_amap_api_key"
    assert result["error"]["retryable"] is False


def test_nearby_business_error(monkeypatch):
    monkeypatch.setattr(nearby, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        nearby,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "0", "info": "INVALID_USER_KEY"}, "error": None},
    )

    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "中餐厅",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "amap_nearby_failed"
    assert result["error"]["retryable"] is False


def test_nearby_propagates_network_timeout(monkeypatch):
    monkeypatch.setattr(nearby, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        nearby,
        "request_json_with_retry",
        lambda **_kwargs: {
            "success": False,
            "data": None,
            "error": {"message": "http_request_timeout", "detail": "slow", "retryable": True},
        },
    )

    result = nearby.search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "中餐厅",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "http_request_timeout"
    assert result["error"]["retryable"] is True
