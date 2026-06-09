from langchain_core.tools import tool

from .base import fail, ok


@tool
def nearby_tool(
    location: str,
    city: str,
    types: str = "",
    keyword: str = "",
    radius: int = 5000,
    offset: int = 20,
    page: int = 1,
):
    """Wrapped nearby POI tool with a unified result schema."""
    try:
        from tools.nearby import search_nearby_poi as original_search_nearby_poi

        result = original_search_nearby_poi.invoke(
            {
                "location": location,
                "city": city,
                "types": types,
                "keyword": keyword,
                "radius": radius,
                "offset": offset,
                "page": page,
            }
        )
    except Exception as exc:
        return fail("nearby_search_failed", str(exc))

    if isinstance(result, str):
        return fail("nearby_search_empty", result)
    return ok(result)
