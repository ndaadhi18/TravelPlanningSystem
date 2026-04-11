"""
LangGraph definition for PLANIT orchestration (M18).
"""

from __future__ import annotations

from typing import Any, Mapping

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.agents.accommodation_agent import accommodation_node
from backend.agents.constraint_agent import constraint_node
from backend.agents.greeting_agent import greeting_node
from backend.agents.local_expert_agent import local_expert_node
from backend.agents.payment_agent import payment_node
from backend.agents.transport_agent import transport_node
from backend.orchestration.router import (
    normalize_feedback_type,
    route_after_constraint,
    route_after_feedback,
    route_after_greeting,
    route_after_planning,
)
from backend.orchestration.state import TravelState
from backend.schemas.travel_state import FeedbackType, PlanningPhase


async def planning_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """
    Minimal deterministic planning node for M18 graph wiring.
    """
    iteration_count = _to_int(state.get("iteration_count"), default=0)
    feedback_type = normalize_feedback_type(state.get("feedback_type"))
    if feedback_type == FeedbackType.MODIFY.value:
        iteration_count += 1

    return {
        "current_phase": PlanningPhase.DATA_GATHERING,
        "iteration_count": iteration_count,
    }


def feedback_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """
    Human-in-the-loop node that pauses graph execution for user feedback.
    """
    resume_payload = interrupt(
        {
            "status": "awaiting_feedback",
            "current_phase": PlanningPhase.FEEDBACK.value,
            "itinerary": state.get("itinerary"),
            "budget_summary": state.get("budget_summary"),
        }
    )

    updates: dict[str, Any] = {
        "current_phase": PlanningPhase.FEEDBACK,
    }

    if isinstance(resume_payload, Mapping):
        feedback_text = resume_payload.get("feedback")
        if isinstance(feedback_text, str) and feedback_text.strip():
            updates["feedback"] = feedback_text.strip()

        normalized_feedback_type = normalize_feedback_type(
            resume_payload.get("feedback_type")
        )
        if normalized_feedback_type is not None:
            updates["feedback_type"] = normalized_feedback_type
    elif isinstance(resume_payload, str) and resume_payload.strip():
        updates["feedback"] = resume_payload.strip()

    return updates


def build_state_graph() -> StateGraph:
    """
    Build the uncompiled state graph.
    """
    graph = StateGraph(TravelState)

    graph.add_node("greeting", greeting_node)
    graph.add_node("planning", planning_node)
    graph.add_node("transport", transport_node)
    graph.add_node("accommodation", accommodation_node)
    graph.add_node("local_expert", local_expert_node)
    graph.add_node("constraint", constraint_node)
    graph.add_node("feedback", feedback_node)
    graph.add_node("payment", payment_node)

    graph.add_edge(START, "greeting")
    graph.add_conditional_edges("greeting", route_after_greeting)

    graph.add_conditional_edges("planning", route_after_planning)
    graph.add_edge("transport", "constraint")
    graph.add_edge("accommodation", "constraint")
    graph.add_edge("local_expert", "constraint")

    graph.add_conditional_edges("constraint", route_after_constraint)
    graph.add_conditional_edges("feedback", route_after_feedback)
    graph.add_edge("payment", END)

    return graph


def build_graph():
    """
    Build and compile the orchestration graph.
    """
    return build_state_graph().compile()


def _to_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "build_graph",
    "build_state_graph",
    "feedback_node",
    "planning_node",
]
