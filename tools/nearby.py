from typing import Annotated

from langchain_core.tools import tool

from settings import get_settings
from tools.base import fail, ok, request_json_with_retry
from utils.redis_cache import make_cache_key, redis_cache


@tool
def search_nearby_poi(
    location: Annotated[str, "中心点坐标，以“,”分割，经度在前，纬度在后，如117.500244,40.417801"],
    city: Annotated[str, "查询中心点所在的城市编码。"],
    types: Annotated[str, "查询POI类型。多个类型用“|”分割。如果查询住宿，只能填写以下类型：“宾馆酒店”“旅馆招待所”。如果查询餐饮，只能填写以下类型：“中餐厅”“外国餐厅”“快餐厅”。关键字和POI类型二者至少填写一个。"] = "",
    keyword: Annotated[str, "要搜索的关键字。除非用户有特别指定具体的地点名称时才填写，如“星巴克”“希尔顿”等，否则不要填写！一次只能搜索一个关键字。关键字和POI类型二者至少填写一个。"] = "",
    radius: Annotated[int, "查询半径，单位米。"] = 5000,
    offset: Annotated[int, "每页搜索结果数目。"] = 20,
    page: Annotated[int, "当前页数。"] = 1,
) -> dict:
    """周边搜索工具。根据中心点坐标和关键字或POI类型搜索周边POI。返回结果中，距离的单位都是米，费用的单位都是元。"""

    if keyword == "" and types == "":
        return fail(
            "invalid_poi_query",
            "关键字和 POI 类型至少填写一个",
            retryable=False,
        )

    amap_key = get_settings().amap_api_key
    if not amap_key:
        return fail("missing_amap_api_key", "缺少 AMAP_API_KEY 环境变量", retryable=False)

    cache_payload = {
        "location": location,
        "city": city,
        "types": types,
        "keyword": keyword,
        "radius": radius,
        "offset": offset,
        "page": page,
    }
    cache_key = make_cache_key("nearby_poi", cache_payload)
    cached = redis_cache.get_json(cache_key)
    if cached is not None:
        return cached

    base_url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": amap_key,
        "location": location,
        "keywords": keyword,
        "types": types,
        "city": city,
        "radius": radius,
        "offset": offset,
        "page": page,
    }
    response = request_json_with_retry(
        tool_name="search_nearby_poi",
        url=base_url,
        params=params,
        safe_log_params={
            "location": location,
            "city": city,
            "types": types,
            "has_keyword": bool(keyword),
            "radius": radius,
            "offset": offset,
            "page": page,
        },
    )
    if not response["success"]:
        return response

    result = response["data"]
    poi = keyword or types
    if result.get("status") == "0":
        return fail(
            "amap_nearby_failed",
            f"在{location}周边搜索{poi}失败。错误信息: {result.get('info', 'UNKNOWN_ERROR')}",
            retryable=False,
        )

    pois = result.get("pois", [])
    if not pois:
        return fail(
            "nearby_poi_empty",
            f"在{location}周边没有搜索到{poi}相关结果。尝试扩大搜索半径或者更换关键字或POI类型。",
            retryable=False,
        )

    nearby_search_result = {
        "source": "amap",
        "fallback_used": False,
        "center_point": location,
        "search_result_count": result.get("count", "0"),
        "pois": [],
    }

    for item in pois:
        biz_ext = item.get("biz_ext") or {}
        nearby_search_result["pois"].append({
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "address": item.get("address", ""),
            "distance": item.get("distance", ""),
            "location": item.get("location", ""),
            "rating": biz_ext.get("rating") or "not available",
            "cost": biz_ext.get("cost") or "not available",
        })
    result = ok(nearby_search_result)
    redis_cache.set_json(cache_key, result)
    return result


if __name__ == "__main__":
    print(search_nearby_poi.args_schema.model_json_schema())
    a = search_nearby_poi.invoke({
        "location": "113.129362,29.371356",
        "city": "0730",
        "types": "旅馆招待所|中餐厅",
    })
    print(a)
