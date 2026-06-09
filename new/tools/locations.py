from langchain_core.tools import tool

from .base import fail, ok


@tool
def location_tool(location: str, city: str = ""):
    """Wrapped geocoding tool with a unified result schema."""
    try:
        from tools.locations import get_location_coordinate as original_get_location_coordinate

        result = original_get_location_coordinate.invoke(
            {
                "location": location,
                "city": city,
            }
        )
    except Exception as exc:
        return fail("location_invoke_failed", str(exc))

    if isinstance(result, list) and result and isinstance(result[0], dict) and result[0].get("error"):
        return fail("location_lookup_failed", result[0])
    return ok(result)
