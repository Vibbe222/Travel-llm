import json
from functools import lru_cache
from typing import Any, AsyncGenerator

from dotenv import find_dotenv, load_dotenv
from langchain_core.messages import HumanMessage

from new.graph.graph import init_app
from utils.helper import get_thread_id

DEFAULT_MODEL_NAME = "deepseek-v4-flash"
DEFAULT_RECURSION_LIMIT = 60

_ = load_dotenv(find_dotenv())


@lru_cache(maxsize=2)
def get_app(model_name: str = DEFAULT_MODEL_NAME):
    return init_app(model_name=model_name)


def build_config(thread_id: str | None = None) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": thread_id or get_thread_id()},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }


async def iter_chat_events(
    user_message: str,
    config: dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
) -> AsyncGenerator[dict[str, Any], None]:
    app = get_app(model_name=model_name)
    async for event in app.astream_events(
        {"messages": [HumanMessage(content=user_message)]},
        config=config,
        version="v1",
    ):
        normalized = _normalize_event(event)
        if normalized is not None:
            yield normalized
    yield {"type": "done"}


async def iter_chat_event_lines(
    user_message: str,
    config: dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
) -> AsyncGenerator[str, None]:
    try:
        async for event in iter_chat_events(
            user_message=user_message,
            config=config,
            model_name=model_name,
        ):
            yield json.dumps(_json_safe(event), ensure_ascii=False) + "\n"
    except Exception as exc:
        yield json.dumps(
            {
                "type": "error",
                "error": {
                    "message": str(exc),
                    "class_name": exc.__class__.__name__,
                },
            },
            ensure_ascii=False,
        ) + "\n"


def _normalize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    kind = event.get("event")

    if kind == "on_chat_model_stream":
        content = event["data"]["chunk"].content
        if content:
            return {"type": "chunk", "content": content}
        return None

    if kind == "on_chain_end" and event.get("name") == "final_responder":
        messages = event["data"].get("output", {}).get("messages", [])
        if messages:
            message = messages[-1]
            content = getattr(message, "content", "")
            if content:
                return {"type": "chunk", "content": content}
        return None

    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "content"):
        return getattr(value, "content", "")
    return str(value)
