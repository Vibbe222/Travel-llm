from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class TravelPlannerState(TypedDict, total=False):
    """Structured state shared by the multi-node travel planning graph."""

    messages: Annotated[list, add_messages]
    intent_type: str
    selected_destination: str
    user_constraints: dict[str, Any]
    candidate_destinations: list[dict[str, Any]]
    attractions: list[dict[str, Any]]
    daily_plan: list[dict[str, Any]]
    transport_segments: list[dict[str, Any]]
    meal_options: list[dict[str, Any]]
    hotel_options: list[dict[str, Any]]
    validation_issues: list[dict[str, Any]]
    final_status: str
    needs_clarification: bool
    needs_replan: bool
    replan_attempts: int


class PublicState(TravelPlannerState, total=False):
    """Backward-compatible alias for older imports."""
