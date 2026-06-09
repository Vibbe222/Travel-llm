from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from new.graph.nodes import build_nodes

from new.graph.routers import (
    route_after_destination,
    route_after_intent,
    route_after_transport,
)
from new.states.state import TravelPlannerState


def create_graph(model_name: str):
    graph = StateGraph(TravelPlannerState)
    nodes = build_nodes(model_name=model_name)

    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "intent_router")
    graph.add_conditional_edges("intent_router", route_after_intent)
    graph.add_conditional_edges("destination_clarifier", route_after_destination)
    graph.add_edge("attraction_collector", "itinerary_planner")
    graph.add_edge("itinerary_planner", "transport_validator")
    graph.add_conditional_edges("transport_validator", route_after_transport)
    graph.add_edge("poi_enricher", "final_responder")
    graph.add_edge("final_responder", END)
    return graph


def init_app(model_name: str):
    graph = create_graph(model_name=model_name)
    memory = InMemorySaver()
    return graph.compile(checkpointer=memory)
