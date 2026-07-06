import json
import logging
import traceback
import warnings
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict

from dotenv import find_dotenv, load_dotenv
from langchain_core._api.beta_decorator import LangChainBetaWarning
from langchain_core.messages import HumanMessage

from utils.helper import get_thread_id

DEFAULT_MODEL_NAME = "deepseek-v4-flash"
DEFAULT_RECURSION_LIMIT = 60
STREAMING_RESPONSE_NODE = "final_responder"
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
_ = load_dotenv(find_dotenv())


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


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any] | None:
    # 作用：把底层事件整理成统一格式，方便前端或接口层消费。
    # 将底层框架事件转换成前端更容易消费的统一结构。
    kind = event["event"]

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
        return {
            "type": "tool_end",
            "name": event["name"],
            "output": event["data"].get("output"),
        }

    return None


def _json_safe(value: Any) -> Any:
    # 作用：把复杂对象转换成可被 JSON 序列化的普通数据。
    # 递归清洗复杂对象，确保最终都能被 JSON 序列化。
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

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

    async for event in app.astream_events(
        {"messages": formatted_user_message},
        config=config,
        version="v1",
    ):
        normalized = _normalize_event(event)
        if normalized is not None:
            yield normalized

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
            "error": {
                "message": str(exc),
                "class_name": exc.__class__.__name__,
            },
        }
        yield json.dumps(error_event, ensure_ascii=False) + "\n"

