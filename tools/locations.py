import os
from typing import Annotated, Dict, List

import requests
from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import tool

MAX_COORD_QUERY_PER_SPOT = 3
_LOCATION_QUERY_COUNTER: Dict[str, int] = {}


@tool
def get_location_coordinate(
    location: Annotated[str, "要获取经纬度的地点名称"],
    city: Annotated[str, "地点所在的地级市名称，可选"] = "",
) -> List[Dict[str, str]]:
    """位置获取工具。根据地点名称和城市名称获取该地点的经纬度。"""

    key = f"{city.strip()}::{location.strip()}"
    current_count = _LOCATION_QUERY_COUNTER.get(key, 0) + 1
    _LOCATION_QUERY_COUNTER[key] = current_count
    if current_count > MAX_COORD_QUERY_PER_SPOT:
        return [{
            "address": "",
            "coordinate": "",
            "citycode": "",
            "error": (
                f"地点“{location}”（城市：{city or '未知'}）坐标查询已超过上限"
                f"（最多 {MAX_COORD_QUERY_PER_SPOT} 次）。"
            ),
        }]

    _ = load_dotenv(find_dotenv())
    amap_key = os.getenv("AMAP_API_KEY")

    if not amap_key:
        return [{
            "address": "",
            "coordinate": "",
            "citycode": "",
            "error": "缺少 AMAP_API_KEY 环境变量",
        }]

    base_url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": amap_key,
        "address": location,
        "city": city,
    }

    try:
        r = requests.get(base_url, params=params, timeout=15)
        r.raise_for_status()
        result = r.json()
    except Exception as exc:
        return [{
            "address": "",
            "coordinate": "",
            "citycode": "",
            "error": f"请求坐标接口失败：{location}，错误：{exc}",
        }]

    if result.get("status") != "1":
        return [{
            "address": "",
            "coordinate": "",
            "citycode": "",
            "error": f"获取地点坐标失败：{location}，错误信息：{result.get('info', 'UNKNOWN_ERROR')}",
        }]

    geocodes = result.get("geocodes", [])
    if not geocodes:
        return [{
            "address": "",
            "coordinate": "",
            "citycode": "",
            "error": f"未找到地点坐标：{location}",
        }]

    location_coordinates: List[Dict[str, str]] = []
    for item in geocodes:
        location_coordinates.append({
            "address": item.get("formatted_address", ""),
            "coordinate": item.get("location", ""),
            "citycode": item.get("citycode", ""),
        })

    return location_coordinates


if __name__ == "__main__":
    print(get_location_coordinate.args_schema.model_json_schema())
    print(get_location_coordinate.invoke({"location": "三坊七巷", "city": "福州"}))
