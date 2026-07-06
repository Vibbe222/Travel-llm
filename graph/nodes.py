import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agents.stage_executor import StageExecutor
from prompts.clarify import CLARIFY_PROMPT
from prompts.finalize import FINALIZE_PROMPT
from prompts.intent import INTENT_PROMPT
from prompts.planner import PLANNER_PROMPT
from prompts.validation import VALIDATION_PROMPT
from tools import (
    get_attractions_information,
    get_location_coordinate,
    route_planning,
    search_nearby_poi,
    web_search,
)


class ToolBundle:
    def __init__(self):
        self.web_search = web_search
        self.attractions = get_attractions_information
        self.location = get_location_coordinate
        self.route = route_planning
        self.nearby = search_nearby_poi


def build_nodes(model_name: str, tools: ToolBundle | None = None) -> dict[str, Any]:
    tool_bundle = tools or ToolBundle()
    return {
        "intent_router": IntentRouterNode(model_name),
        "destination_clarifier": DestinationClarifierNode(model_name, tool_bundle),
        "attraction_collector": AttractionCollectorNode(tool_bundle),
        "itinerary_planner": ItineraryPlannerNode(model_name),
        "transport_validator": TransportValidatorNode(model_name, tool_bundle),
        "poi_enricher": PoiEnricherNode(tool_bundle),
        "final_responder": FinalResponderNode(model_name),
    }


class IntentRouterNode:
    def __init__(self, model_name: str):
        self.executor = StageExecutor(
            model_name=model_name,
            prompt_template=INTENT_PROMPT,
            expects_json=True,
            fallback=_fallback_intent_result,
        )

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        latest_user = _latest_user_message(state)
        result = await self.executor.run(state, latest_user_message=latest_user)

        intent_type = result.get("intent_type") or _infer_intent_type(latest_user, state)
        selected_destination = (
            result.get("selected_destination")
            or state.get("selected_destination")
            or _extract_destination(latest_user)
        )
        constraints = dict(state.get("user_constraints", {}))
        constraints.update(_extract_constraints(latest_user))
        if isinstance(result.get("user_constraints"), dict):
            constraints.update(result["user_constraints"])

        needs_clarification = not bool(selected_destination)
        validation_issues = list(state.get("validation_issues", []))
        if needs_clarification:
            validation_issues.append(
                {
                    "stage": "intent_router",
                    "message": "未从用户输入中识别出明确目的地，需要先澄清或给出候选目的地。",
                }
            )

        return {
            "intent_type": intent_type,
            "selected_destination": selected_destination or "",
            "user_constraints": constraints,
            "needs_clarification": needs_clarification,
            "final_status": "routing",
            "validation_issues": validation_issues,
        }


class DestinationClarifierNode:
    def __init__(self, model_name: str, tools: ToolBundle | None = None):
        self.tools = tools or ToolBundle()
        self.executor = StageExecutor(
            model_name=model_name,
            prompt_template=CLARIFY_PROMPT,
            fallback=lambda state: {"content": ""},
        )

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        latest_user = _latest_user_message(state)
        tool_result = self.tools.web_search.invoke(
            {
                "keywords": f"{latest_user} 旅游 城市 推荐",
                "max_results": 5,
            }
        )

        candidate_destinations = []
        validation_issues = list(state.get("validation_issues", []))
        if tool_result.get("success"):
            for item in tool_result.get("data", {}).get("results", [])[:3]:
                candidate_destinations.append(
                    {
                        "name": item.get("title", "")[:30] or item.get("href", ""),
                        "url": item.get("href", ""),
                        "snippet": item.get("body", ""),
                    }
                )
        else:
            validation_issues.append(
                {
                    "stage": "destination_clarifier",
                    "message": "目的地候选搜索失败。",
                    "detail": tool_result.get("error"),
                }
            )

        selected_destination = state.get("selected_destination") or _extract_destination(latest_user)
        if not selected_destination and candidate_destinations:
            llm_result = await self.executor.run(
                state,
                candidate_destinations=json.dumps(candidate_destinations, ensure_ascii=False, indent=2),
            )
            selected_destination = _extract_destination(llm_result.get("content", "")) or candidate_destinations[0]["name"]

        response_message = (
            f"当前需求里没有明确目的地，我先给出候选方向："
            f"{'；'.join(item['name'] for item in candidate_destinations) or '暂无可用候选'}。"
            f"参考版默认先按“{selected_destination or '待确认目的地'}”继续。"
        )

        return {
            "candidate_destinations": candidate_destinations,
            "selected_destination": selected_destination or "",
            "needs_clarification": not bool(selected_destination),
            "validation_issues": validation_issues,
            "final_status": "clarified" if selected_destination else "need_user_input",
            "messages": [AIMessage(content=response_message)] if candidate_destinations else [],
        }


class AttractionCollectorNode:
    def __init__(self, tools: ToolBundle | None = None):
        self.tools = tools or ToolBundle()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        destination = state.get("selected_destination", "").strip()
        if not destination:
            return {
                "validation_issues": list(state.get("validation_issues", []))
                + [{"stage": "attraction_collector", "message": "没有可用目的地，无法采集景点。"}],
                "attractions": [],
            }

        attraction_result = self.tools.attractions.invoke({"destination": destination})
        attractions = []
        validation_issues = list(state.get("validation_issues", []))

        if attraction_result.get("success"):
            scenic_list = attraction_result.get("data", {}).get("scenic_list", [])
            for spot in scenic_list[:5]:
                attraction = {
                    "name": spot.get("name", ""),
                    "summary": spot.get("summary", ""),
                    "duration": spot.get("duration", ""),
                    "open_time": spot.get("open_time", ""),
                    "address": "",
                    "coordinate": "",
                    "citycode": "",
                }

                coord_result = self.tools.location.invoke(
                    {
                        "location": attraction["name"],
                        "city": destination,
                    }
                )
                locations = coord_result.get("data", {}).get("locations", []) if coord_result.get("success") else []
                if locations:
                    coord = locations[0]
                    attraction["address"] = coord.get("address", "")
                    attraction["coordinate"] = coord.get("coordinate", "")
                    attraction["citycode"] = coord.get("citycode", "")
                else:
                    validation_issues.append(
                        {
                            "stage": "attraction_collector",
                            "message": f"景点“{attraction['name']}”坐标补全失败。",
                            "detail": coord_result.get("error"),
                        }
                    )
                attractions.append(attraction)
        else:
            validation_issues.append(
                {
                    "stage": "attraction_collector",
                    "message": "景点采集失败。",
                    "detail": attraction_result.get("error"),
                }
            )

        if not attractions:
            validation_issues.append(
                {
                    "stage": "attraction_collector",
                    "message": "未拿到可用景点，后续规划会退化成占位流程。",
                }
            )

        return {
            "attractions": attractions,
            "validation_issues": validation_issues,
            "final_status": "attractions_collected",
        }


class ItineraryPlannerNode:
    def __init__(self, model_name: str):
        self.executor = StageExecutor(
            model_name=model_name,
            prompt_template=PLANNER_PROMPT,
            expects_json=True,
            fallback=_fallback_plan_result,
        )

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        replan_attempts = state.get("replan_attempts", 0)
        attractions = list(state.get("attractions", []))
        if replan_attempts > 0 and len(attractions) > 3:
            attractions = attractions[:3]

        llm_result = await self.executor.run(
            {**state, "attractions": attractions},
            selected_destination=state.get("selected_destination", ""),
            user_constraints=json.dumps(state.get("user_constraints", {}), ensure_ascii=False),
        )
        daily_plan = llm_result.get("daily_plan") or _build_fallback_daily_plan(attractions)

        return {
            "daily_plan": daily_plan,
            "needs_replan": False,
            "final_status": "itinerary_planned",
        }


class TransportValidatorNode:
    def __init__(self, model_name: str, tools: ToolBundle | None = None):
        self.tools = tools or ToolBundle()
        self.executor = StageExecutor(
            model_name=model_name,
            prompt_template=VALIDATION_PROMPT,
            fallback=lambda state: {"content": ""},
        )

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        validation_issues = list(state.get("validation_issues", []))
        transport_segments = []
        needs_replan = False

        for day in state.get("daily_plan", []):
            spots = day.get("spots", [])
            for first, second in zip(spots, spots[1:]):
                if not first.get("coordinate") or not second.get("coordinate"):
                    continue

                route_result = self.tools.route.invoke(
                    {
                        "origin": first["coordinate"],
                        "destination": second["coordinate"],
                        "origin_city_code": first.get("citycode", ""),
                        "dest_city_code": second.get("citycode", ""),
                    }
                )

                if not route_result.get("success"):
                    needs_replan = True
                    validation_issues.append(
                        {
                            "stage": "transport_validator",
                            "message": f"{first['name']} 到 {second['name']} 的交通查询失败。",
                            "detail": route_result.get("error"),
                        }
                    )
                    continue

                route_data = route_result.get("data", {})
                segment = {
                    "day": day.get("day"),
                    "from": first["name"],
                    "to": second["name"],
                    "route": route_data,
                }
                transport_segments.append(segment)

                try:
                    walking_distance = int(route_data.get("walking_distance", "0"))
                except Exception:
                    walking_distance = 0
                if walking_distance > 12000:
                    needs_replan = True
                    validation_issues.append(
                        {
                            "stage": "transport_validator",
                            "message": f"{first['name']} 到 {second['name']} 的步行距离过长，建议重排行程。",
                            "detail": route_data,
                        }
                    )

        await self.executor.run(
            state,
            transport_summary=json.dumps(transport_segments, ensure_ascii=False, indent=2),
        )

        return {
            "transport_segments": transport_segments,
            "validation_issues": validation_issues,
            "needs_replan": needs_replan,
            "replan_attempts": state.get("replan_attempts", 0) + (1 if needs_replan else 0),
            "final_status": "transport_validated" if not needs_replan else "needs_replan",
        }


class PoiEnricherNode:
    def __init__(self, tools: ToolBundle | None = None):
        self.tools = tools or ToolBundle()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        meal_options = []
        hotel_options = []
        validation_issues = list(state.get("validation_issues", []))
        last_spot = _get_last_spot(state)
        if not last_spot or not last_spot.get("coordinate"):
            return {
                "meal_options": meal_options,
                "hotel_options": hotel_options,
                "validation_issues": validation_issues,
                "final_status": "poi_skipped",
            }

        citycode = last_spot.get("citycode", "")
        coordinate = last_spot["coordinate"]

        food_result = self.tools.nearby.invoke(
            {
                "location": coordinate,
                "city": citycode,
                "types": "中餐厅|快餐厅",
                "radius": 3000,
                "offset": 5,
                "page": 1,
            }
        )
        if food_result.get("success"):
            meal_options = food_result.get("data", {}).get("pois", [])[:3]
        else:
            validation_issues.append(
                {
                    "stage": "poi_enricher",
                    "message": "餐饮推荐查询失败。",
                    "detail": food_result.get("error"),
                }
            )

        hotel_result = self.tools.nearby.invoke(
            {
                "location": coordinate,
                "city": citycode,
                "types": "宾馆酒店|旅馆招待所",
                "radius": 4000,
                "offset": 5,
                "page": 1,
            }
        )
        if hotel_result.get("success"):
            hotel_options = hotel_result.get("data", {}).get("pois", [])[:3]
        else:
            validation_issues.append(
                {
                    "stage": "poi_enricher",
                    "message": "住宿推荐查询失败。",
                    "detail": hotel_result.get("error"),
                }
            )

        return {
            "meal_options": meal_options,
            "hotel_options": hotel_options,
            "validation_issues": validation_issues,
            "final_status": "poi_enriched",
        }


class FinalResponderNode:
    def __init__(self, model_name: str):
        self.executor = StageExecutor(
            model_name=model_name,
            prompt_template=FINALIZE_PROMPT,
            fallback=_fallback_final_result,
        )

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        llm_result = await self.executor.run(state)
        content = llm_result.get("content") or _render_final_markdown(state)
        return {
            "messages": [AIMessage(content=content)],
            "final_status": "completed",
        }


def _latest_user_message(state: dict[str, Any]) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content
        if getattr(message, "type", "") == "human":
            return getattr(message, "content", "")
    return ""


def _extract_destination(text: str) -> str:
    match = re.search(r"(?:去|到|在)([\u4e00-\u9fa5]{2,8})(?:旅游|旅行|玩|逛|待|攻略|一日游|两日游|三日游)?", text)
    if match:
        return match.group(1)
    return ""


def _extract_constraints(text: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    day_match = re.search(r"(\d+)天", text)
    if day_match:
        constraints["days"] = int(day_match.group(1))
    if "亲子" in text:
        constraints["style"] = "亲子"
    elif "轻松" in text:
        constraints["style"] = "轻松"
    elif "特种兵" in text:
        constraints["style"] = "高强度"
    if "预算" in text:
        constraints["budget_note"] = text
    if "酒店" in text or "住宿" in text:
        constraints["hotel_note"] = text
    if "餐" in text or "吃" in text:
        constraints["meal_note"] = text
    return constraints


def _infer_intent_type(text: str, state: dict[str, Any]) -> str:
    if any(token in text for token in ["修改", "调整", "改成", "不要", "减少", "增加"]):
        return "modify"
    if any(token in text for token in ["确认", "就这样", "可以", "没问题"]) and state.get("daily_plan"):
        return "confirm"
    return "new_plan"


def _fallback_intent_result(state: dict[str, Any]) -> dict[str, Any]:
    latest_user = _latest_user_message(state)
    return {
        "intent_type": _infer_intent_type(latest_user, state),
        "selected_destination": _extract_destination(latest_user),
        "user_constraints": _extract_constraints(latest_user),
    }


def _build_fallback_daily_plan(attractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not attractions:
        return [
            {
                "day": 1,
                "theme": "占位行程",
                "spots": [],
                "notes": "当前没有采集到景点，这里只保留了参考版行程骨架。",
            }
        ]

    days = []
    chunk_size = 2
    for index in range(0, len(attractions), chunk_size):
        chunk = attractions[index:index + chunk_size]
        formatted_spots = []
        start_hour = 9
        for offset, spot in enumerate(chunk):
            formatted_spots.append(
                {
                    "name": spot.get("name", ""),
                    "coordinate": spot.get("coordinate", ""),
                    "citycode": spot.get("citycode", ""),
                    "open_time": spot.get("open_time", ""),
                    "duration": spot.get("duration", ""),
                    "time_range": f"{start_hour + offset * 3:02d}:00-{start_hour + offset * 3 + 2:02d}:00",
                    "summary": spot.get("summary", ""),
                }
            )
        days.append(
            {
                "day": len(days) + 1,
                "theme": "按景点顺序生成的参考版行程",
                "spots": formatted_spots,
                "notes": "这是基于景点顺序的示例安排，后续可继续结合时长、开放时间和交通做更细排程。",
            }
        )
    return days


def _fallback_plan_result(state: dict[str, Any]) -> dict[str, Any]:
    return {"daily_plan": _build_fallback_daily_plan(state.get("attractions", []))}


def _fallback_final_result(state: dict[str, Any]) -> dict[str, Any]:
    return {"content": _render_final_markdown(state)}


def _render_final_markdown(state: dict[str, Any]) -> str:
    lines = []
    destination = state.get("selected_destination") or "待确认目的地"
    lines.append(f"# {destination} 参考版旅游规划")
    lines.append("")
    lines.append("## 每日行程")
    for day in state.get("daily_plan", []):
        lines.append(f"### Day {day.get('day')}: {day.get('theme', '参考行程')}")
        for spot in day.get("spots", []):
            lines.append(
                f"- {spot.get('time_range', '待定')} {spot.get('name', '未命名景点')}"
                f" | 开放时间：{spot.get('open_time', '未知')}"
                f" | 预计停留：{spot.get('duration', '未知')}"
            )
        if day.get("notes"):
            lines.append(f"- 备注：{day['notes']}")
        lines.append("")

    if state.get("transport_segments"):
        lines.append("## 交通校验")
        for segment in state["transport_segments"]:
            route = segment.get("route", {})
            lines.append(
                f"- Day {segment.get('day')} {segment.get('from')} -> {segment.get('to')}"
                f"：步行距离 {route.get('walking_distance', '未知')} 米，"
                f"公交方案数 {len(route.get('public_transport_options_list', []))}"
            )
        lines.append("")

    if state.get("meal_options") or state.get("hotel_options"):
        lines.append("## 周边推荐")
        for item in state.get("meal_options", [])[:3]:
            lines.append(f"- 餐饮：{item.get('name', '')} | {item.get('address', '')}")
        for item in state.get("hotel_options", [])[:3]:
            lines.append(f"- 住宿：{item.get('name', '')} | {item.get('address', '')}")
        lines.append("")

    if state.get("validation_issues"):
        lines.append("## 过程中的校验提示")
        for issue in state["validation_issues"][-5:]:
            lines.append(f"- [{issue.get('stage', 'unknown')}] {issue.get('message', '')}")

    return "\n".join(lines)


def _get_last_spot(state: dict[str, Any]) -> dict[str, Any] | None:
    for day in reversed(state.get("daily_plan", [])):
        spots = day.get("spots", [])
        if spots:
            return spots[-1]
    return None
