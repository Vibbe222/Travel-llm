from langgraph.graph import END, START, StateGraph

from graph.checkpoint import build_checkpointer
from graph.nodes import build_nodes
from graph.routers import route_after_destination, route_after_intent, route_after_transport
from states.state import TravelPlannerState


def create_graph(model_name, is_async=True):
    graph = StateGraph(TravelPlannerState)
    nodes = build_nodes(model_name=model_name)

    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "intent_router")
    graph.add_conditional_edges("intent_router", route_after_intent)
    graph.add_edge("clarification_responder", END)
    graph.add_conditional_edges("destination_clarifier", route_after_destination)
    graph.add_edge("attraction_collector", "itinerary_planner")
    graph.add_edge("itinerary_planner", "transport_validator")
    graph.add_conditional_edges("transport_validator", route_after_transport)
    graph.add_edge("poi_enricher", "final_responder")
    graph.add_edge("final_responder", END)
    return graph


def init_app(model_name, is_async=True):
    graph = create_graph(model_name=model_name, is_async=is_async)
    return graph.compile(checkpointer=build_checkpointer())
