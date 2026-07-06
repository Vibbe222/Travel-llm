import json
import logging
import traceback
import warnings
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict

from langchain_core._api.beta_decorator import LangChainBetaWarning
from langchain_core.messages import HumanMessage

from settings import get_settings
from utils.helper import get_thread_id

DEFAULT_MODEL_NAME = get_settings().model_name
DEFAULT_RECURSION_LIMIT = 60
STREAMING_RESPONSE_NODE = "final_responder"
logger = logging.getLogger(__name__)

NODE_PROGRESS_START = {
    "intent_router": "正在理解旅行需求",
    "clarification_responder": "正在确认缺失信息",
    "destination_clarifier": "正在补全目的地信息",
    "attraction_collector": "正在获取景点信息",
    "itinerary_planner": "正在生成行程草案",
    "transport_validator": "正在校验交通可行性",
    "poi_enricher": "正在补充餐饮和住宿建议",
    "final_responder": "正在整理最终回复",
}

NODE_PROGRESS_DONE = {
    "intent_router": "已识别旅行需求",
    "clarification_responder": "已生成澄清问题",
    "destination_clarifier": "已整理目的地候选",
    "attraction_collector": "已获取景点信息",
    "itinerary_planner": "已生成行程草案",
    "transport_validator": "已完成交通校验",
    "poi_enricher": "已补充周边推荐",
    "final_responder": "已生成最终回复",
}

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "key",
    "token",
    "authorization",
    "password",
    "secret",
    "prompt",
    "state_summary",
    "messages",
}

TOOL_COMPONENTS = {
    "get_attractions_information": "景点主数据源抓取组件（get_attractions_information / Selenium）",
    "get_location_coordinate": "地点坐标解析组件（get_location_coordinate / AMap）",
    "route_planning": "交通路线规划组件（route_planning / AMap）",
    "search_nearby_poi": "周边 POI 查询组件（search_nearby_poi / AMap）",
    "web_search": "网页搜索组件（web_search / DuckDuckGo）",
}

warnings.filterwarnings("ignore", category=LangChainBetaWarning)


@lru_cache(maxsize=4)
# 装饰器作用：缓存函数返回结果，避免同一模型重复初始化应用实例。
def get_app(model_name: str = DEFAULT_MODEL_NAME):
    # 按模型缓存应用实例，避免每次对话都重复初始化图。
    from graph.graph import init_app

    return init_app(model_name=model_name)


def build_config(thread_id: str | None = None) -> Dict[str, Any]:
    # 作用：构造一次对话运行需要的配置。
    # 将 thread_id 放入 configurable，便于复用同一会话上下文。
    return {
        "configurable": {"thread_id": thread_id or get_thread_id()},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }


def create_session(model_name: str = DEFAULT_MODEL_NAME) -> Dict[str, Any]:
    # 作用：创建并返回上层可直接使用的会话信息。
    # 同时返回 thread_id 和 config，方便上层直接保存和透传会话信息。
    config = build_config()
    return {
        "thread_id": config["configurable"]["thread_id"],
        "config": config,
        "model_name": model_name,
    }


def _event_node_name(event: Dict[str, Any]) -> str | None:
    metadata = event.get("metadata") or {}
    node_name = metadata.get("langgraph_node")
    if node_name:
        return str(node_name)

    checkpoint_ns = metadata.get("langgraph_checkpoint_ns")
    if isinstance(checkpoint_ns, str) and checkpoint_ns:
        return checkpoint_ns.split(":", 1)[0]

    return None


def _make_progress(node_name: str | None, phase: str) -> Dict[str, Any] | None:
    if not node_name:
        return None

    message_by_phase = NODE_PROGRESS_START if phase == "start" else NODE_PROGRESS_DONE
    message = message_by_phase.get(node_name)
    if not message:
        return None

    return {
        "type": "progress",
        "stage": node_name,
        "message": message,
    }


def _unwrap_event_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    current = value
    for key in ("output", "state"):
        nested = current.get(key)
        if isinstance(nested, dict):
            current = nested

    return current


def _format_days(days: Any) -> str:
    try:
        number = int(days)
    except Exception:
        return "本次"
    return f"{number}天" if number > 0 else "本次"


def _build_user_plan_preface(output: dict[str, Any]) -> str | None:
    payload = _unwrap_event_output(output)
    if payload.get("needs_clarification"):
        return None

    destination = str(payload.get("selected_destination") or "").strip()
    if not destination:
        return None

    constraints = payload.get("user_constraints") if isinstance(payload.get("user_constraints"), dict) else {}
    day_text = _format_days(constraints.get("days"))

    return (
        f"任务：用户明确想去{destination}游玩{day_text}，需要获取{destination}的景点信息。\n"
        f"回顾：用户描述了本次旅行需求，目的地已明确为“{destination}”。\n"
        f"分析：需要先获取{destination}的景点信息，包括景点简介、开放时间和预计游玩时间等。\n"
        f"计划：调用“景点搜索工具”获取{destination}的景点列表。\n\n"
    )


def _split_preface_chunks(content: str) -> list[str]:
    if not content:
        return []
    lines = content.splitlines(keepends=True)
    chunks = []
    for line in lines:
        if line:
            chunks.append(line)
    return chunks or [content]


def _extract_ai_message_content(output: dict[str, Any]) -> str:
    payload = _unwrap_event_output(output)
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""

    for message in reversed(messages):
        if hasattr(message, "content"):
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def _user_readable_tool_error(tool_name: str, output: Any) -> str:
    error = output.get("error") if isinstance(output, dict) else None
    message = error.get("message") if isinstance(error, dict) else None

    if message == "missing_amap_api_key":
        return "地图服务暂不可用，部分坐标、交通或周边推荐可能缺失。"
    if message in {"http_request_timeout", "web_search_timeout"}:
        return "外部数据服务响应超时，当前结果可能不完整。"
    if message in {"http_temporary_error", "http_connection_error"}:
        return "外部数据服务暂时不可用，当前结果可能不完整。"
    if message in {"location_not_found", "nearby_poi_empty", "web_search_empty"}:
        return "没有查到足够的外部数据，当前结果会更多依赖已有信息。"
    return f"{tool_name} 工具调用失败，当前结果可能不完整。"


def _tool_error_event(tool_name: str, output: Any) -> Dict[str, Any] | None:
    if not isinstance(output, dict) or output.get("success") is not False:
        return None

    error = output.get("error") or {}
    return {
        "type": "tool_error",
        "tool": tool_name,
        "user_message": _user_readable_tool_error(tool_name, output),
        "debug": {
            "tool": tool_name,
            "error_type": error.get("message") if isinstance(error, dict) else "tool_failed",
            "retryable": error.get("retryable") if isinstance(error, dict) else None,
            "detail": error.get("detail") if isinstance(error, dict) else error,
        },
        "raw": _json_safe(output),
    }


def _degradation_event(tool_name: str, output: Any) -> Dict[str, Any] | None:
    if not isinstance(output, dict) or not output.get("success"):
        return None

    data = output.get("data")
    if not isinstance(data, dict):
        return None

    fallback_used = bool(data.get("fallback_used"))
    warnings_list = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    source = str(data.get("source") or "")
    cache_hint = bool(data.get("cache_used") or data.get("stale_cache_used"))
    component = TOOL_COMPONENTS.get(tool_name, f"{tool_name} 组件")

    if not fallback_used and not warnings_list and not cache_hint:
        return None

    if fallback_used:
        warning_text = str(warnings_list[0]) if warnings_list else ""
        if tool_name == "get_attractions_information" and (
            "Selenium" in warning_text or "WebDriver" in warning_text or source == "web_search_fallback"
        ):
            reason = "Chrome WebDriver 启动或页面抓取失败，已改用网页搜索结果。"
        elif warning_text:
            reason = warning_text
        else:
            reason = "主数据源不可用，已改用备用数据来源。"
        impact = "景点详情、开放时间或停留时长可能不如主数据源完整。"
        confidence = "中等"
    elif cache_hint:
        reason = "实时数据不可用，已使用缓存数据。"
        impact = "价格、营业状态或交通信息可能不是最新。"
        confidence = "中等偏低"
    else:
        reason = str(warnings_list[0]) if warnings_list else "部分数据不完整。"
        impact = "结果中相关字段可能缺失或需要人工确认。"
        confidence = "中等"

    return {
        "type": "degradation",
        "stage": "tool",
        "tool": tool_name,
        "component": component,
        "reason": reason,
        "impact": impact,
        "confidence": confidence,
        "debug": {
            "stage": "tool",
            "tool": tool_name,
            "component": component,
            "error_type": "fallback_used" if fallback_used else "partial_data",
            "source": source,
            "warnings": warnings_list,
        },
        "raw": _json_safe(output),
    }


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any] | None:
    # 作用：把底层事件整理成统一格式，方便前端或接口层消费。
    # 将底层框架事件转换成前端更容易消费的统一结构。
    kind = event["event"]

    if kind == "on_chain_start":
        return _make_progress(_event_node_name(event), "start")

    if kind == "on_chain_end":
        return _make_progress(_event_node_name(event), "done")

    if kind == "on_chat_model_stream":
        node_name = _event_node_name(event)
        if node_name and node_name != STREAMING_RESPONSE_NODE:
            return None

        content = event["data"]["chunk"].content
        if content:
            # 过滤空分片，只向外输出真正的模型内容。
            return {"type": "chunk", "content": content}
        return None

    if kind == "on_tool_start":
        return {
            "type": "tool_start",
            "name": event["name"],
            "input": event["data"].get("input"),
        }

    if kind == "on_tool_end":
        output = event["data"].get("output")
        return {
            "type": "tool_end",
            "name": event["name"],
            "output": output,
        }

    return None


def _json_safe(value: Any) -> Any:
    # 作用：把复杂对象转换成可被 JSON 序列化的普通数据。
    # 递归清洗复杂对象，确保最终都能被 JSON 序列化。
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_KEYS:
                cleaned[key_text] = "[已隐藏]"
            else:
                cleaned[key_text] = _json_safe(item)
        return cleaned

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump())
        except Exception:
            return str(value)

    if hasattr(value, "dict"):
        try:
            return _json_safe(value.dict())
        except Exception:
            return str(value)

    if hasattr(value, "content"):
        try:
            return _json_safe(value.content)
        except Exception:
            return str(value)

    return str(value)


async def iter_chat_events(
    user_message: str,
    config: Dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
) -> AsyncGenerator[Dict[str, Any], None]:
    # 作用：流式执行对话，并逐条产出标准化事件。
    # 将用户输入包装成 HumanMessage，并持续产出标准化后的事件。
    app = get_app(model_name=model_name)
    formatted_user_message = HumanMessage(content=user_message)

    yield {
        "type": "progress",
        "stage": "request",
        "message": "已收到请求，正在识别目的地",
    }
    preface_sent = False
    clarification_sent = False

    async for event in app.astream_events(
        {"messages": formatted_user_message},
        config=config,
        version="v1",
    ):
        normalized = _normalize_event(event)
        if normalized is not None:
            yield normalized
            if event.get("event") == "on_chain_end":
                node_name = _event_node_name(event)
                output = event.get("data", {}).get("output")
                if node_name == "intent_router" and not preface_sent:
                    preface = _build_user_plan_preface(output if isinstance(output, dict) else {})
                    if preface:
                        preface_sent = True
                        for chunk in _split_preface_chunks(preface):
                            yield {"type": "chunk", "content": chunk}
                elif node_name == "clarification_responder" and not clarification_sent:
                    content = _extract_ai_message_content(output if isinstance(output, dict) else {})
                    if content:
                        clarification_sent = True
                        yield {"type": "chunk", "content": content}
            if normalized.get("type") == "tool_end":
                tool_name = str(normalized.get("name") or "")
                output = normalized.get("output")
                degradation = _degradation_event(tool_name, output)
                if degradation is not None:
                    yield degradation
                tool_error = _tool_error_event(tool_name, output)
                if tool_error is not None:
                    yield tool_error

    yield {"type": "done"}


async def iter_chat_event_lines(
    user_message: str,
    config: Dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
) -> AsyncGenerator[str, None]:
    # 作用：把事件流转成按行输出的 JSON 字符串流。
    try:
        # 以 JSON Lines 形式输出，方便流式 HTTP 或 SSE 按行消费。
        async for event in iter_chat_events(
            user_message=user_message,
            config=config,
            model_name=model_name,
        ):
            yield json.dumps(_json_safe(event), ensure_ascii=False) + "\n"
    except Exception as exc:
        logger.exception(
            "chat stream failed. thread_id=%s model_name=%s user_message=%r\n%s",
            config.get("configurable", {}).get("thread_id"),
            model_name,
            user_message,
            traceback.format_exc(),
        )
        # 流式场景下不直接抛异常，而是返回统一的错误事件。
        error_event = {
            "type": "error",
            "user_message": "生成过程中出现异常，本次回复未能完整完成。",
            "debug": {
                "message": str(exc),
                "class_name": exc.__class__.__name__,
            },
            "raw": {
                "traceback": traceback.format_exc(),
            },
        }
        yield json.dumps(_json_safe(error_event), ensure_ascii=False) + "\n"

