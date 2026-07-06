import time
from typing import Annotated, Any, Dict, List

import requests
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from langchain_core.tools import tool

from settings import get_settings
from tools.base import fail, get_tool_logger, ok
from utils.redis_cache import make_cache_key, redis_cache

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@tool
def web_search(
    keywords: Annotated[str, "要搜索的关键词"],
    max_results: Annotated[int, "最多返回多少条搜索结果"] = 10,
) -> dict:
    """网络搜索工具。在搜索引擎上搜索关键词，返回结果列表。"""

    logger = get_tool_logger("web_search")
    settings = get_settings()
    provider = settings.web_search_provider
    cache_key = make_cache_key("web_search", {
        "provider": provider,
        "keywords": keywords,
        "max_results": max_results,
    })
    cached = redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    if provider == "tavily":
        return _search_with_tavily(
            keywords=keywords,
            max_results=max_results,
            cache_key=cache_key,
            logger=logger,
        )

    return _search_with_duckduckgo(
        keywords=keywords,
        max_results=max_results,
        cache_key=cache_key,
        logger=logger,
    )


def _search_with_tavily(
    *,
    keywords: str,
    max_results: int,
    cache_key: str,
    logger,
) -> dict:
    settings = get_settings()
    if not settings.tavily_api_key:
        return fail("missing_tavily_api_key", "缺少 TAVILY_API_KEY 环境变量", retryable=False)

    started_at = time.perf_counter()
    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": keywords,
                "search_depth": "advanced",
                "max_results": max_results,
            },
            timeout=settings.request_timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)

        if response.status_code == 429:
            logger.warning(
                "tool=web_search provider=tavily status=rate_limited elapsed_ms=%s params=%s",
                elapsed_ms,
                {"max_results": max_results, "keyword_length": len(keywords)},
            )
            return fail("tavily_rate_limited", "Tavily 搜索接口限流", retryable=True)

        if response.status_code in {401, 403}:
            return fail("tavily_auth_failed", "Tavily API key 无效或无权限", retryable=False)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "tool=web_search provider=tavily status=http_failed http_status=%s elapsed_ms=%s params=%s",
                response.status_code,
                elapsed_ms,
                {"max_results": max_results, "keyword_length": len(keywords)},
            )
            return fail("tavily_search_failed", f"HTTP {response.status_code}: {exc}", retryable=False)

        try:
            payload = response.json()
        except ValueError as exc:
            return fail("tavily_invalid_response", str(exc), retryable=False)

        results = payload.get("results")
        if not isinstance(results, list):
            return fail("tavily_invalid_response", "Tavily 响应中缺少 results 列表", retryable=False)

        mapped_results = []
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            mapped_results.append({
                "title": item.get("title", ""),
                "href": item.get("url", ""),
                "body": item.get("content", ""),
                "score": item.get("score"),
            })

        if not mapped_results:
            return fail("web_search_empty", "搜索结果为空", retryable=False)

        result = ok({
            "source": "tavily",
            "fallback_used": False,
            "results": mapped_results,
        })
        redis_cache.set_json(cache_key, result)
        logger.info(
            "tool=web_search provider=tavily status=success elapsed_ms=%s params=%s",
            elapsed_ms,
            {"max_results": max_results, "keyword_length": len(keywords)},
        )
        return result
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "tool=web_search provider=tavily status=retryable_error elapsed_ms=%s params=%s",
            elapsed_ms,
            {"max_results": max_results, "keyword_length": len(keywords)},
        )
        return fail("tavily_search_timeout", str(exc), retryable=True)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.error(
            "tool=web_search provider=tavily status=failed elapsed_ms=%s params=%s",
            elapsed_ms,
            {"max_results": max_results, "keyword_length": len(keywords)},
        )
        return fail("tavily_search_failed", str(exc), retryable=False)


def _search_with_duckduckgo(
    *,
    keywords: str,
    max_results: int,
    cache_key: str,
    logger,
) -> dict:
    max_attempts = 3
    backoffs = [1, 2]
    last_error = ""

    for attempt in range(max_attempts):
        started_at = time.perf_counter()
        try:
            with DDGS() as ddgs:
                results: List[Dict[str, Any]] = [
                    r for r in ddgs.text(
                        keywords=keywords,
                        region="cn-zh",
                        max_results=max_results,
                    )
                ]

            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if not results:
                logger.info(
                    "tool=web_search status=empty elapsed_ms=%s params=%s",
                    elapsed_ms,
                    {"max_results": max_results, "keyword_length": len(keywords)},
                )
                return fail("web_search_empty", "搜索结果为空", retryable=False)

            logger.info(
                "tool=web_search status=success elapsed_ms=%s params=%s",
                elapsed_ms,
                {"max_results": max_results, "keyword_length": len(keywords)},
            )
            result = ok({
                "source": "duckduckgo",
                "fallback_used": False,
                "results": results,
            })
            redis_cache.set_json(cache_key, result)
            return result
        except (DuckDuckGoSearchException, requests.exceptions.Timeout, TimeoutError, requests.exceptions.ConnectionError) as exc:
            last_error = str(exc)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.warning(
                "tool=web_search status=retryable_error attempt=%s/%s elapsed_ms=%s params=%s",
                attempt + 1,
                max_attempts,
                elapsed_ms,
                {"max_results": max_results, "keyword_length": len(keywords)},
            )
            if attempt < max_attempts - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
            continue
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.error(
                "tool=web_search status=failed elapsed_ms=%s params=%s",
                elapsed_ms,
                {"max_results": max_results, "keyword_length": len(keywords)},
            )
            return fail("web_search_failed", str(exc), retryable=False)

    return fail("web_search_timeout", last_error or "operation timed out", retryable=True)


if __name__ == "__main__":
    print(web_search.args_schema.model_json_schema())
    print(web_search.invoke({"keywords": "福州 旅游"}))
