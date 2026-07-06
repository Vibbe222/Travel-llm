import importlib

from tools import attractions


class FakeWebSearchTool:
    def invoke(self, payload):
        return {
            "success": True,
            "data": {
                "source": "duckduckgo",
                "fallback_used": False,
                "results": [
                    {
                        "title": "福州三坊七巷旅游攻略",
                        "href": "https://example.test/fuzhou",
                        "body": "福州经典历史街区。",
                    }
                ],
            },
            "error": None,
        }


def test_attractions_fallback_when_selenium_fails(monkeypatch):
    def raise_driver_error():
        raise attractions.WebDriverException("chrome failed")

    monkeypatch.setattr(attractions, "InitWebDriver", raise_driver_error)

    web_search_module = importlib.import_module("tools.web_search")

    monkeypatch.setattr(web_search_module, "web_search", FakeWebSearchTool())

    result = attractions.get_attractions_information.invoke({"destination": "福州"})

    assert result["success"] is True
    assert result["data"]["source"] == "web_search_fallback"
    assert result["data"]["fallback_used"] is True
    assert result["data"]["scenic_list"][0]["name"] == "福州三坊七巷旅游攻略"


def test_attractions_limits_scenic_spots_constant():
    assert attractions.MAX_SCENIC_SPOTS == 5


def test_attractions_success_with_mocked_mafengwo_pages(monkeypatch):
    class FakeDriver:
        quit_called = False

        def quit(self):
            self.quit_called = True

    fake_driver = FakeDriver()
    search_html = """
        <div class="search-mdd-wrap">
            <a href="//www.mafengwo.cn/search/s.php?id=123&type=10">福州</a>
        </div>
    """
    destination_html = """
        <span id="mdd_poi_desc">福州是一座历史文化名城。</span>
        <ul class="scenic-list clearfix">
            <li><a href="/poi/1.html"><h3>三坊七巷</h3></a></li>
        </ul>
    """
    detail_html = """
        <div class="summary">福州经典历史街区。</div>
        <li class="item-time"><div class="content">2小时</div></li>
        <dl><dt>开放时间</dt><dd>全天开放</dd></dl>
    """

    def fake_fetch(driver, url):
        assert driver is fake_driver
        if "search/q.php" in url:
            return search_html
        if url == "https://www.mafengwo.cn/jd/123/gonglve.html":
            return destination_html
        if url == "https://www.mafengwo.cn/poi/1.html":
            return detail_html
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(attractions, "InitWebDriver", lambda: fake_driver)
    monkeypatch.setattr(attractions, "fetch_page_with_selenium", fake_fetch)

    result = attractions.get_attractions_information.invoke({"destination": "福州"})

    assert result["success"] is True
    assert result["data"]["source"] == "mafengwo"
    assert result["data"]["fallback_used"] is False
    assert result["data"]["overview"] == "福州是一座历史文化名城。"
    assert result["data"]["scenic_list"][0]["name"] == "三坊七巷"
    assert result["data"]["scenic_list"][0]["duration"] == "2小时"
    assert result["data"]["scenic_list"][0]["open_time"] == "全天开放"
    assert fake_driver.quit_called is True


def test_attractions_fallback_failure_is_explicit(monkeypatch):
    class FailingWebSearchTool:
        def invoke(self, payload):
            return {
                "success": False,
                "data": None,
                "error": {"message": "web_search_timeout", "detail": "slow", "retryable": True},
            }

    def raise_timeout():
        raise attractions.TimeoutException("mafengwo timeout")

    monkeypatch.setattr(attractions, "InitWebDriver", raise_timeout)

    web_search_module = importlib.import_module("tools.web_search")
    monkeypatch.setattr(web_search_module, "web_search", FailingWebSearchTool())

    result = attractions.get_attractions_information.invoke({"destination": "福州"})

    assert result["success"] is False
    assert result["error"]["message"] == "attractions_fallback_failed"
    assert result["error"]["retryable"] is True


def test_attractions_fallback_is_not_cached(monkeypatch):
    cached_values = []
    monkeypatch.setattr(attractions.redis_cache, "set_json", lambda key, value: cached_values.append((key, value)))

    result = {
        "success": True,
        "data": {
            "source": "web_search_fallback",
            "fallback_used": True,
        },
        "error": None,
    }

    attractions._cache_if_primary_source("cache-key", result)

    assert cached_values == []


def test_attractions_primary_source_is_cached(monkeypatch):
    cached_values = []
    monkeypatch.setattr(attractions.redis_cache, "set_json", lambda key, value: cached_values.append((key, value)))

    result = {
        "success": True,
        "data": {
            "source": "mafengwo",
            "fallback_used": False,
        },
        "error": None,
    }

    attractions._cache_if_primary_source("cache-key", result)

    assert cached_values == [("cache-key", result)]
