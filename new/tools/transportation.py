from langchain_core.tools import tool

from .base import fail, ok


@tool
def route_tool(
    origin: str,
    destination: str,
    origin_city_code: str,
    dest_city_code: str,
):
    """Wrapped route planning tool with a unified result schema."""
    try:
        from tools.transportation import route_planning as original_route_planning

        result = original_route_planning.invoke(
            {
                "origin": origin,
                "destination": destination,
                "origin_city_code": origin_city_code,
                "dest_city_code": dest_city_code,
            }
        )
    except Exception as exc:
        return fail("route_planning_failed", str(exc))

    return ok(result)
