from langchain_core.tools import tool

from .base import fail, ok


@tool
def attractions_tool(destination: str):
    """Wrapped attractions tool with a unified result schema."""
    try:
        from tools.attractions import get_attractions_information as original_get_attractions_information

        result = original_get_attractions_information.invoke({"destination": destination})
    except Exception as exc:
        return fail("attractions_lookup_failed", str(exc))

    scenic_list = result.get("scenic_list", []) if isinstance(result, dict) else []
    if not scenic_list:
        return fail("attractions_not_found", result)
    return ok(result)
