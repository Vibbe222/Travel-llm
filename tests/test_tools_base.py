import requests

from tools import base


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_ok_and_fail_shapes():
    assert base.ok({"x": 1}) == {"success": True, "data": {"x": 1}, "error": None}

    result = base.fail("bad", "detail", retryable=True)
    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == {"message": "bad", "detail": "detail", "retryable": True}


def test_request_json_with_retry_retries_temporary_status(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        if len(calls) == 1:
            return FakeResponse(status_code=500, payload={"ignored": True})
        return FakeResponse(status_code=200, payload={"status": "1"})

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _: None)

    result = base.request_json_with_retry(
        tool_name="unit_tool",
        url="https://example.test/api",
        params={"key": "secret"},
        safe_log_params={"city": "0730"},
    )

    assert result["success"] is True
    assert result["data"] == {"status": "1"}
    assert len(calls) == 2
    assert calls[0][2] == 12


def test_request_json_with_retry_does_not_retry_400(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(1)
        return FakeResponse(status_code=400, payload={})

    monkeypatch.setattr(base.requests, "get", fake_get)

    result = base.request_json_with_retry(
        tool_name="unit_tool",
        url="https://example.test/api",
        params={},
    )

    assert result["success"] is False
    assert result["error"]["message"] == "http_request_failed"
    assert result["error"]["retryable"] is False
    assert len(calls) == 1


def test_request_json_with_retry_timeout_returns_retryable_failure(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        raise requests.exceptions.Timeout("slow upstream")

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _: None)

    result = base.request_json_with_retry(
        tool_name="unit_tool",
        url="https://example.test/api",
        params={},
        max_retries=1,
    )

    assert result["success"] is False
    assert result["error"]["message"] == "http_request_timeout"
    assert result["error"]["detail"] == "slow upstream"
    assert result["error"]["retryable"] is True
    assert len(calls) == 2


def test_request_json_with_retry_invalid_json(monkeypatch):
    class InvalidJsonResponse(FakeResponse):
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(
        base.requests,
        "get",
        lambda url, params, timeout: InvalidJsonResponse(status_code=200),
    )

    result = base.request_json_with_retry(
        tool_name="unit_tool",
        url="https://example.test/api",
        params={},
    )

    assert result["success"] is False
    assert result["error"]["message"] == "invalid_json_response"
    assert result["error"]["retryable"] is False
