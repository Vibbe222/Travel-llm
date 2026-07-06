from tools import transportation


def test_route_success_with_warning_for_empty_transits(monkeypatch):
    monkeypatch.setattr(transportation, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")

    monkeypatch.setattr(
        transportation,
        "request_json_with_retry",
        lambda **_kwargs: {
            "success": True,
            "data": {
                "status": "1",
                "route": {
                    "origin": "113.1,29.3",
                    "destination": "113.2,29.4",
                    "distance": "1000",
                    "taxi_cost": "0",
                    "transits": [],
                },
            },
            "error": None,
        },
    )

    result = transportation.route_planning.invoke({
        "origin": "113.1,29.3",
        "destination": "113.2,29.4",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })

    assert result["success"] is True
    assert result["data"]["warnings"] == ["没有可用的公共交通方案。"]
    assert result["data"]["taxi_cost"] == "not available"


def test_route_business_error(monkeypatch):
    monkeypatch.setattr(transportation, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        transportation,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "0", "info": "INVALID_PARAMS"}, "error": None},
    )

    result = transportation.route_planning.invoke({
        "origin": "113.1,29.3",
        "destination": "113.2,29.4",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "amap_route_failed"
    assert result["error"]["retryable"] is False


def test_route_missing_api_key(monkeypatch):
    monkeypatch.setattr(transportation, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)

    result = transportation.route_planning.invoke({
        "origin": "113.1,29.3",
        "destination": "113.2,29.4",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "missing_amap_api_key"
    assert result["error"]["retryable"] is False


def test_route_invalid_schema(monkeypatch):
    monkeypatch.setattr(transportation, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        transportation,
        "request_json_with_retry",
        lambda **_kwargs: {"success": True, "data": {"status": "1"}, "error": None},
    )

    result = transportation.route_planning.invoke({
        "origin": "113.1,29.3",
        "destination": "113.2,29.4",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "amap_route_schema_invalid"
    assert result["error"]["retryable"] is False


def test_route_propagates_network_timeout(monkeypatch):
    monkeypatch.setattr(transportation, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AMAP_API_KEY", "fake")
    monkeypatch.setattr(
        transportation,
        "request_json_with_retry",
        lambda **_kwargs: {
            "success": False,
            "data": None,
            "error": {"message": "http_request_timeout", "detail": "slow", "retryable": True},
        },
    )

    result = transportation.route_planning.invoke({
        "origin": "113.1,29.3",
        "destination": "113.2,29.4",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })

    assert result["success"] is False
    assert result["error"]["message"] == "http_request_timeout"
    assert result["error"]["retryable"] is True
