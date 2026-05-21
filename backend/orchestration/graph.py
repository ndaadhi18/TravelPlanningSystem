"""
LangGraph definition for PLANIT orchestration (M18).
"""

from __future__ import annotations

from typing import Any, Mapping

from langgraph.graph import END, START, StateGraph

from backend.agents.accommodation_agent import accommodation_node
from backend.agents.constraint_agent import constraint_node
from backend.agents.greeting_agent import greeting_node
from backend.agents.local_expert_agent import local_expert_node
from backend.agents.transport_agent import transport_node
from backend.orchestration.router import (
    normalize_feedback_type,
    route_after_constraint,
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


async def _transport_graph_node(state: Mapping[str, Any]) -> dict[str, Any]:
    return await _sanitize_parallel_updates(await transport_node(state))


async def _accommodation_graph_node(state: Mapping[str, Any]) -> dict[str, Any]:
    return await _sanitize_parallel_updates(await accommodation_node(state))


async def _local_expert_graph_node(state: Mapping[str, Any]) -> dict[str, Any]:
    return await _sanitize_parallel_updates(await local_expert_node(state))


def feedback_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """
    Human-in-the-loop checkpoint.
    In the REST API flow, we never reach this node because the graph ends
    at constraint -> END. It is kept for future WebSocket/streaming usage.
    """
    return {
        "current_phase": PlanningPhase.FEEDBACK,
    }


def build_state_graph() -> StateGraph:
    """
    Build the uncompiled state graph.
    """
    graph = StateGraph(TravelState)

    graph.add_node("greeting", greeting_node)
    graph.add_node("planning", planning_node)
    graph.add_node("transport", _transport_graph_node)
    graph.add_node("accommodation", _accommodation_graph_node)
    graph.add_node("local_expert", _local_expert_graph_node)
    graph.add_node("constraint", constraint_node)

    graph.add_edge(START, "greeting")
    graph.add_conditional_edges("greeting", route_after_greeting)
    graph.add_conditional_edges("planning", route_after_planning)
    graph.add_edge("transport", "constraint")
    graph.add_edge("accommodation", "constraint")
    graph.add_edge("local_expert", "constraint")
    graph.add_conditional_edges("constraint", route_after_constraint)

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


async def _sanitize_parallel_updates(updates: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """
    Avoid parallel write conflicts on singleton state keys.
    """
    normalized = dict(updates)
    normalized.pop("current_phase", None)
    return normalized


__all__ = [
    "build_graph",
    "build_state_graph",
    "planning_node",
]
