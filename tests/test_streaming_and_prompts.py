import pytest

import chat_service
from agents.stage_executor import StageExecutor
from prompts.main import PROMPT_REGISTRY
from prompts.planner import PLANNER_PROMPT


class Chunk:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    async def ainvoke(self, _messages):
        return Chunk("不是 JSON")


class FakeApp:
    async def astream_events(self, *_args, **_kwargs):
        yield {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "intent_router"},
            "data": {
                "output": {
                    "selected_destination": "福州",
                    "user_constraints": {"days": 2},
                    "needs_clarification": False,
                }
            },
        }


def test_planner_prompt_json_example_is_escaped_for_str_format():
    rendered = PLANNER_PROMPT.format(
        state_summary="{}",
        selected_destination="福州",
        user_constraints='{"days": 2}',
    )

    assert '"daily_plan"' in rendered
    assert "福州" in rendered


@pytest.mark.anyio
async def test_stage_executor_format_errors_use_fallback():
    executor = StageExecutor(
        model_name="test-model",
        prompt_template="{missing_context}",
        fallback=lambda state: {"daily_plan": []},
    )

    result = await executor.run({"attractions": []})

    assert result["daily_plan"] == []
    assert "fallback_reason" in result


@pytest.mark.anyio
async def test_stage_executor_json_parse_errors_use_fallback(monkeypatch):
    executor = StageExecutor(
        model_name="test-model",
        prompt_template="ok",
        expects_json=True,
        fallback=lambda state: {"daily_plan": []},
    )
    monkeypatch.setattr(executor, "_get_llm", lambda: FakeLLM())

    result = await executor.run({"attractions": []})

    assert result == {"daily_plan": [], "fallback_reason": "json_parse_failed"}


def test_main_prompt_module_is_split_prompt_registry():
    assert set(PROMPT_REGISTRY) == {"intent", "clarify", "planner", "validation", "finalize"}
    assert "工作流程" not in "\n".join(PROMPT_REGISTRY.values())


def test_normalize_event_filters_internal_stage_model_streams():
    event = {
        "event": "on_chat_model_stream",
        "metadata": {"langgraph_node": "intent_router"},
        "data": {"chunk": Chunk('{"intent_type":"new_plan"}')},
    }

    assert chat_service._normalize_event(event) is None


def test_normalize_event_allows_final_responder_model_streams():
    event = {
        "event": "on_chat_model_stream",
        "metadata": {"langgraph_node": "final_responder"},
        "data": {"chunk": Chunk("最终回复")},
    }

    assert chat_service._normalize_event(event) == {"type": "chunk", "content": "最终回复"}


def test_normalize_event_emits_user_facing_progress():
    event = {
        "event": "on_chain_start",
        "metadata": {"langgraph_node": "attraction_collector"},
        "data": {},
    }

    assert chat_service._normalize_event(event) == {
        "type": "progress",
        "stage": "attraction_collector",
        "message": "正在获取景点信息",
    }


def test_tool_degradation_event_detects_fallback_without_secret_leak():
    output = {
        "success": True,
        "data": {
            "source": "web_search_fallback",
            "fallback_used": True,
            "warnings": ["Selenium 景点抓取失败，已降级使用网页搜索。原因摘要：WebDriverException"],
            "api_key": "secret",
        },
        "error": None,
    }

    event = chat_service._degradation_event("get_attractions_information", output)

    assert event["type"] == "degradation"
    assert event["component"] == "景点主数据源抓取组件（get_attractions_information / Selenium）"
    assert "Chrome WebDriver" in event["reason"]
    assert event["confidence"] == "中等"
    assert event["raw"]["data"]["api_key"] == "[已隐藏]"


def test_tool_error_event_has_layered_error_fields():
    output = {
        "success": False,
        "data": None,
        "error": {
            "message": "http_request_timeout",
            "detail": "slow upstream",
            "retryable": True,
        },
    }

    event = chat_service._tool_error_event("route_planning", output)

    assert event["type"] == "tool_error"
    assert "响应超时" in event["user_message"]
    assert event["debug"]["error_type"] == "http_request_timeout"
    assert event["raw"]["error"]["detail"] == "slow upstream"


def test_build_user_plan_preface_uses_safe_template():
    content = chat_service._build_user_plan_preface(
        {
            "selected_destination": "福州",
            "user_constraints": {"days": 2},
            "needs_clarification": False,
        }
    )

    assert content.startswith("任务：用户明确想去福州游玩2天")
    assert "分析：需要先获取福州的景点信息" in content
    assert "计划：调用“景点搜索工具”获取福州的景点列表。" in content
    assert "{" not in content


def test_build_user_plan_preface_skips_clarification_state():
    assert chat_service._build_user_plan_preface({"needs_clarification": True}) is None


def test_split_preface_chunks_streams_line_by_line():
    chunks = chat_service._split_preface_chunks(
        "任务：A\n回顾：B\n分析：C\n计划：D\n\n"
    )

    assert chunks == ["任务：A\n", "回顾：B\n", "分析：C\n", "计划：D\n", "\n"]


@pytest.mark.anyio
async def test_iter_chat_events_emits_preface_after_intent_router(monkeypatch):
    monkeypatch.setattr(chat_service, "get_app", lambda model_name: FakeApp())

    events = [
        event
        async for event in chat_service.iter_chat_events(
            user_message="福州两天怎么玩",
            config={"configurable": {"thread_id": "t1"}},
            model_name="test-model",
        )
    ]

    chunks = [event["content"] for event in events if event["type"] == "chunk"]

    assert any("任务：用户明确想去福州游玩2天" in chunk for chunk in chunks)
    assert any(chunk.startswith("回顾：") for chunk in chunks)
    assert not any("任务：" in chunk and "回顾：" in chunk for chunk in chunks)
    assert events[-1] == {"type": "done"}
