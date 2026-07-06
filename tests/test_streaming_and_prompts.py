import pytest

import chat_service
from agents.stage_executor import StageExecutor
from prompts.planner import PLANNER_PROMPT


class Chunk:
    def __init__(self, content):
        self.content = content


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
