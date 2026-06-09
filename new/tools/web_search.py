from langchain_core.tools import tool

from .base import fail, ok


@tool
def web_search_tool(keywords: str, max_results: int = 10):
    """Wrapped web search tool with a unified result schema."""
    try:
        from tools.web_search import web_search as original_web_search

        result = original_web_search.invoke(
            {
                "keywords": keywords,
                "max_results": max_results,
            }
        )
    except Exception as exc:
        return fail("web_search_invoke_failed", str(exc))

    if isinstance(result, list) and result and isinstance(result[0], dict) and result[0].get("error"):
        return fail(result[0]["error"], result[0])
    return ok(result)
