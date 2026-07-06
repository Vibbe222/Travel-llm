import importlib
from types import SimpleNamespace

web_search = importlib.import_module("tools.web_search")


class FakeDDGS:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def text(self, keywords, region, max_results):
        return [
            {"title": "福州旅游", "href": "https://example.test", "body": "三坊七巷推荐"}
        ]


class EmptyDDGS(FakeDDGS):
    def text(self, keywords, region, max_results):
        return []


def test_web_search_success(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is True
    assert result["data"]["source"] == "duckduckgo"
    assert result["data"]["results"][0]["title"] == "福州旅游"


def test_web_search_empty(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(web_search, "DDGS", EmptyDDGS)

    result = web_search.web_search.invoke({"keywords": "不存在的关键词", "max_results": 3})

    assert result["success"] is False
    assert result["error"]["message"] == "web_search_empty"
    assert result["error"]["retryable"] is False


def test_web_search_network_timeout(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "duckduckgo")

    class TimeoutDDGS(FakeDDGS):
        calls = 0

        def text(self, keywords, region, max_results):
            TimeoutDDGS.calls += 1
            raise TimeoutError("duckduckgo timeout")

    monkeypatch.setattr(web_search, "DDGS", TimeoutDDGS)
    monkeypatch.setattr(web_search.time, "sleep", lambda _: None)

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is False
    assert result["error"]["message"] == "web_search_timeout"
    assert result["error"]["retryable"] is True
    assert TimeoutDDGS.calls == 3


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise web_search.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_web_search_tavily_success(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")

    def fake_post(url, json, timeout):
        assert url == web_search.TAVILY_SEARCH_URL
        assert json["api_key"] == "fake-tavily-key"
        assert json["query"] == "福州 旅游"
        assert json["search_depth"] == "advanced"
        return FakeResponse(
            200,
            {
                "results": [
                    {
                        "title": "福州旅游攻略",
                        "url": "https://example.test/fuzhou",
                        "content": "三坊七巷和西湖公园推荐。",
                        "score": 0.9,
                    }
                ]
            },
        )

    monkeypatch.setattr(web_search.requests, "post", fake_post)

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is True
    assert result["data"]["source"] == "tavily"
    assert result["data"]["results"][0] == {
        "title": "福州旅游攻略",
        "href": "https://example.test/fuzhou",
        "body": "三坊七巷和西湖公园推荐。",
        "score": 0.9,
    }


def test_web_search_tavily_requires_api_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is False
    assert result["error"]["message"] == "missing_tavily_api_key"
    assert result["error"]["retryable"] is False


def test_web_search_tavily_rate_limited(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
    monkeypatch.setattr(
        web_search.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=429),
    )

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is False
    assert result["error"]["message"] == "tavily_rate_limited"
    assert result["error"]["retryable"] is True
