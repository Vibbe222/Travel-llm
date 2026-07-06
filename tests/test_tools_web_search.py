import importlib

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
    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    result = web_search.web_search.invoke({"keywords": "福州 旅游", "max_results": 3})

    assert result["success"] is True
    assert result["data"]["source"] == "duckduckgo"
    assert result["data"]["results"][0]["title"] == "福州旅游"


def test_web_search_empty(monkeypatch):
    monkeypatch.setattr(web_search, "DDGS", EmptyDDGS)

    result = web_search.web_search.invoke({"keywords": "不存在的关键词", "max_results": 3})

    assert result["success"] is False
    assert result["error"]["message"] == "web_search_empty"
    assert result["error"]["retryable"] is False


def test_web_search_network_timeout(monkeypatch):
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
