import os
from typing import Annotated, Dict, List

from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import tool

from tools.base import fail, ok, request_json_with_retry

MAX_COORD_QUERY_PER_SPOT = 3
_LOCATION_QUERY_COUNTER: Dict[str, int] = {}


@tool
def get_location_coordinate(
    location: Annotated[str, "要获取经纬度的地点名称"],
    city: Annotated[str, "地点所在的地级市名称，可选"] = "",
) -> dict:
    """位置获取工具。根据地点名称和城市名称获取该地点的经纬度。"""

    key = f"{city.strip()}::{location.strip()}"
    current_count = _LOCATION_QUERY_COUNTER.get(key, 0) + 1
    _LOCATION_QUERY_COUNTER[key] = current_count
    if current_count > MAX_COORD_QUERY_PER_SPOT:
        return fail(
            "location_query_limit_exceeded",
            (
                f"地点“{location}”（城市：{city or '未知'}）坐标查询已超过上限"
                f"（最多 {MAX_COORD_QUERY_PER_SPOT} 次）。"
            ),
            retryable=False,
        )

    _ = load_dotenv(find_dotenv())
    amap_key = os.getenv("AMAP_API_KEY")

    if not amap_key:
        return fail("missing_amap_api_key", "缺少 AMAP_API_KEY 环境变量", retryable=False)

    base_url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": amap_key,
        "address": location,
        "city": city,
    }

    response = request_json_with_retry(
        tool_name="get_location_coordinate",
        url=base_url,
        params=params,
        safe_log_params={"location": location, "city": city},
    )
    if not response["success"]:
        return response

    result = response["data"]
    if result.get("status") != "1":
        return fail(
            "amap_geocode_failed",
            f"获取地点坐标失败：{location}，错误信息：{result.get('info', 'UNKNOWN_ERROR')}",
            retryable=False,
        )

    geocodes = result.get("geocodes", [])
    if not geocodes:
        return fail("location_not_found", f"未找到地点坐标：{location}", retryable=False)

    location_coordinates: List[Dict[str, str]] = []
    for item in geocodes:
        location_coordinates.append({
            "address": item.get("formatted_address", ""),
            "coordinate": item.get("location", ""),
            "citycode": item.get("citycode", ""),
        })

    return ok({
        "source": "amap",
        "fallback_used": False,
        "locations": location_coordinates,
    })


if __name__ == "__main__":
    print(get_location_coordinate.args_schema.model_json_schema())
    print(get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"}))
