import os
from typing import Annotated

from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import tool

from tools.base import fail, ok, request_json_with_retry


@tool
def route_planning(
    origin: Annotated[str, "出发点的经纬度，以“,”分割，经度在前，纬度在后，如117.500244,40.417801"],
    destination: Annotated[str, "目的地的经纬度，以“,”分割，经度在前，纬度在后，如117.500244,40.417801"],
    origin_city_code: Annotated[str, "出发点所在的城市编码"],
    dest_city_code: Annotated[str, "目的地所在的城市编码。"],
) -> dict:
    """路线规划工具。规划综合各类公共交通方式（火车、公交、地铁）的交通方案，返回从出发点到目的地的步行距离、出租车费用以及公共交通方案列表。返回结果中，距离的单位都是米，时间的单位都是秒，费用的单位都是元。如果返回的公共交通方案列表为空，说明两个地点之间没有可用的公共交通方式。"""
    _ = load_dotenv(find_dotenv())
    amap_key = os.getenv("AMAP_API_KEY")
    if not amap_key:
        return fail("missing_amap_api_key", "缺少 AMAP_API_KEY 环境变量", retryable=False)

    base_url = "https://restapi.amap.com/v3/direction/transit/integrated"
    params = {
        "origin": origin,
        "destination": destination,
        "city": origin_city_code,
        "cityd": dest_city_code,
        "key": amap_key,
    }
    response = request_json_with_retry(
        tool_name="route_planning",
        url=base_url,
        params=params,
        safe_log_params={
            "origin": origin,
            "destination": destination,
            "origin_city_code": origin_city_code,
            "dest_city_code": dest_city_code,
        },
    )
    if not response["success"]:
        return response

    result = response["data"]
    if result.get("status") == "0":
        return fail(
            "amap_route_failed",
            f"获取从{origin}到{destination}的交通方案失败。错误信息: {result.get('info', 'UNKNOWN_ERROR')}",
            retryable=False,
        )

    route = result.get("route")
    if not isinstance(route, dict):
        return fail("amap_route_schema_invalid", "高德路线接口响应中缺少 route 字段", retryable=False)

    transits = route.get("transits") or []
    warnings = []
    if not transits:
        warnings.append("没有可用的公共交通方案。")

    routes = {
        "source": "amap",
        "fallback_used": False,
        "warnings": warnings,
        "origin": route.get("origin", origin),
        "destination": route.get("destination", destination),
        "walking_distance": route.get("distance", ""),
        "taxi_cost": route.get("taxi_cost") if route.get("taxi_cost") != "0" else "not available",
        "public_transport_options_list": [],
    }

    for item in transits:
        routes["public_transport_options_list"].append({
            "cost": item.get("cost", ""),
            "duration": item.get("duration", ""),
            "walking_distance": item.get("walking_distance", ""),
        })
    return ok(routes)


if __name__ == "__main__":
    print(route_planning.args_schema.model_json_schema())
    a = route_planning.invoke({
        "origin": "113.129362,29.371356",
        "destination": "112.960976,28.184095",
        "origin_city_code": "0730",
        "dest_city_code": "0730",
    })
    print(a)
