import time
from typing import Annotated, Any, Dict, List

import requests
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from langchain_core.tools import tool

from tools.base import fail, get_tool_logger, ok
from utils.redis_cache import make_cache_key, redis_cache


@tool
def web_search(
    keywords: Annotated[str, "要搜索的关键词"],
    max_results: Annotated[int, "最多返回多少条搜索结果"] = 10,
) -> dict:
    """网络搜索工具。在搜索引擎上搜索关键词，返回结果列表。"""

    logger = get_tool_logger("web_search")
    cache_key = make_cache_key("web_search", {"keywords": keywords, "max_results": max_results})
    cached = redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

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
