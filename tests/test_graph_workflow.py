import pytest
from langchain_core.messages import HumanMessage

from graph.graph import create_graph
from graph.nodes import (
    AttractionCollectorNode,
    PoiEnricherNode,
    TransportValidatorNode,
    _build_fallback_daily_plan,
)
from graph.routers import route_after_destination, route_after_intent, route_after_transport
from states.state import PublicState, TravelPlannerState


class FakeTool:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if callable(self.result):
            return self.result(payload)
        return self.result


class FakeTools:
    def __init__(self):
        self.web_search = FakeTool({"success": True, "data": {"results": []}, "error": None})
        self.attractions = FakeTool(
            {
                "success": True,
                "data": {
                    "scenic_list": [
                        {
                            "name": "三坊七巷",
                            "summary": "历史街区",
                            "duration": "2小时",
                            "open_time": "全天",
                        }
                    ]
                },
                "error": None,
            }
        )
        self.location = FakeTool(
            {
                "success": True,
                "data": {
                    "locations": [
                        {
                            "address": "福建省福州市三坊七巷",
                            "coordinate": "119.296,26.082",
                            "citycode": "0591",
                        }
                    ]
                },
                "error": None,
            }
        )
        self.route = FakeTool(
            {
                "success": True,
                "data": {
                    "walking_distance": "800",
                    "public_transport_options_list": [{"duration": "600"}],
                },
                "error": None,
            }
        )
        self.nearby = FakeTool(
            {
                "success": True,
                "data": {
                    "pois": [
                        {
                            "name": "测试餐厅",
                            "address": "测试路1号",
                            "distance": "100",
                            "rating": "4.6",
                        }
                    ]
                },
                "error": None,
            }
        )


def test_structured_state_contains_phase_three_fields():
    annotations = TravelPlannerState.__annotations__

    for field in [
        "selected_destination",
        "user_constraints",
        "attractions",
        "daily_plan",
        "transport_segments",
        "meal_options",
        "hotel_options",
        "validation_issues",
    ]:
        assert field in annotations

    assert issubclass(PublicState, dict)


def test_workflow_routes():
    assert route_after_intent({"needs_clarification": True}) == "destination_clarifier"
    assert route_after_intent({"selected_destination": "福州"}) == "attraction_collector"
    assert route_after_intent({"intent_type": "confirm", "daily_plan": [{"day": 1}]}) == "final_responder"
    assert route_after_destination({"selected_destination": "福州"}) == "attraction_collector"
    assert route_after_destination({}) == "final_responder"
    assert route_after_transport({"needs_replan": True, "replan_attempts": 1}) == "itinerary_planner"
    assert route_after_transport({"needs_replan": True, "replan_attempts": 2}) == "poi_enricher"


def test_create_graph_compiles_without_initializing_llm():
    app = create_graph("test-model").compile()

    assert app is not None


@pytest.mark.anyio
async def test_attraction_collector_persists_tool_results_to_state():
    tools = FakeTools()
    node = AttractionCollectorNode(tools)

    result = await node({"selected_destination": "福州", "messages": [HumanMessage(content="去福州玩一天")]})

    assert result["final_status"] == "attractions_collected"
    assert result["attractions"][0]["name"] == "三坊七巷"
    assert result["attractions"][0]["coordinate"] == "119.296,26.082"
    assert tools.attractions.calls == [{"destination": "福州"}]
    assert tools.location.calls[0] == {"location": "三坊七巷", "city": "福州"}


@pytest.mark.anyio
async def test_transport_validator_persists_segments(monkeypatch):
    tools = FakeTools()
    node = TransportValidatorNode("test-model", tools)
    monkeypatch.setattr(node.executor, "run", lambda *_args, **_kwargs: _async_result({"content": "ok"}))

    result = await node(
        {
            "daily_plan": [
                {
                    "day": 1,
                    "spots": [
                        {"name": "A", "coordinate": "1,1", "citycode": "001"},
                        {"name": "B", "coordinate": "2,2", "citycode": "001"},
                    ],
                }
            ]
        }
    )

    assert result["final_status"] == "transport_validated"
    assert result["needs_replan"] is False
    assert result["transport_segments"][0]["from"] == "A"
    assert result["transport_segments"][0]["to"] == "B"


@pytest.mark.anyio
async def test_poi_enricher_persists_meals_and_hotels():
    tools = FakeTools()
    node = PoiEnricherNode(tools)

    result = await node(
        {
            "daily_plan": [
                {
                    "day": 1,
                    "spots": [
                        {"name": "三坊七巷", "coordinate": "119.296,26.082", "citycode": "0591"}
                    ],
                }
            ]
        }
    )

    assert result["final_status"] == "poi_enriched"
    assert result["meal_options"][0]["name"] == "测试餐厅"
    assert result["hotel_options"][0]["name"] == "测试餐厅"
    assert len(tools.nearby.calls) == 2


def test_fallback_daily_plan_uses_structured_spots():
    plan = _build_fallback_daily_plan(
        [
            {
                "name": "三坊七巷",
                "coordinate": "119.296,26.082",
                "citycode": "0591",
                "open_time": "全天",
                "duration": "2小时",
                "summary": "历史街区",
            }
        ]
    )

    assert plan[0]["spots"][0]["name"] == "三坊七巷"
    assert plan[0]["spots"][0]["time_range"] == "09:00-11:00"


async def _async_result(value):
    return value
