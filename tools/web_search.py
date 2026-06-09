import time
from typing import Annotated, List, Dict, Any

import requests
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from langchain_core.tools import tool


@tool
def web_search(
    keywords: Annotated[str, "要搜索的关键词"],
    max_results: Annotated[int, "最多返回多少条搜索结果"] = 10,
) -> List[Dict[str, Any]]:
    """网络搜索工具。在搜索引擎上搜索关键词，返回结果列表。"""

    max_attempts = 3
    backoffs = [1, 2, 4]
    last_error = ""

    for attempt in range(max_attempts):
        try:
            with DDGS() as ddgs:
                results = [
                    r for r in ddgs.text(
                        keywords=keywords,
                        region="cn-zh",
                        max_results=max_results,
                    )
                ]
            return results
        except (DuckDuckGoSearchException, requests.exceptions.Timeout, TimeoutError) as exc:
            last_error = str(exc)
            if attempt < max_attempts - 1:
                time.sleep(backoffs[attempt])
            continue
        except Exception as exc:
            return [{
                "error": "web_search_failed",
                "keywords": keywords,
                "source": "duckduckgo",
                "detail": str(exc),
            }]

    return [{
        "error": "web_search_timeout",
        "keywords": keywords,
        "source": "duckduckgo",
        "detail": last_error or "operation timed out",
    }]


if __name__ == "__main__":
    print(web_search.args_schema.model_json_schema())
    print(web_search.invoke({"keywords": "福州 旅游"}))
