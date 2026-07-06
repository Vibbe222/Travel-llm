from typing import Literal


def route_after_intent(state) -> Literal[
    "clarification_responder",
    "destination_clarifier",
    "attraction_collector",
    "itinerary_planner",
    "final_responder",
]:
    if state.get("intent_type") == "confirm" and state.get("daily_plan"):
        return "final_responder"

    if state.get("needs_clarification"):
        return "clarification_responder"

    if state.get("selected_destination") and state.get("attractions"):
        return "itinerary_planner"

    return "attraction_collector"


def route_after_destination(state) -> Literal["attraction_collector", "final_responder"]:
    if state.get("selected_destination"):
        return "attraction_collector"
    return "final_responder"


def route_after_transport(state) -> Literal["itinerary_planner", "poi_enricher"]:
    if state.get("needs_replan") and state.get("replan_attempts", 0) <= 1:
        return "itinerary_planner"
    return "poi_enricher"
