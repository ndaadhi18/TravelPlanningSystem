"""
Routing helpers for LangGraph conditional edges (M18).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from backend.schemas.travel_state import FeedbackType


def route_after_greeting(state: Mapping[str, Any]) -> str:
    """
    Route based on whether greeting extracted a confirmed intent.
    """
    return "planning" if bool(state.get("intent_confirmed")) else "greeting"


def route_after_planning(_state: Mapping[str, Any]) -> list[str]:
    """
    Fan-out routing for parallel data-gathering agents.
    """
    return ["transport", "accommodation", "local_expert"]


def route_after_constraint(_state: Mapping[str, Any]) -> str:
    """
    Move into feedback/human-in-the-loop stage after itinerary assembly.
    """
    return "feedback"


def route_after_feedback(state: Mapping[str, Any]) -> str:
    """
    Route after user feedback is provided.
    """
    iteration_count = _to_int(state.get("iteration_count"), default=0)
    if iteration_count > 5:
        return "payment"

    feedback_type = normalize_feedback_type(state.get("feedback_type"))
    if feedback_type == FeedbackType.APPROVE.value:
        return "payment"
    if feedback_type == FeedbackType.MODIFY.value:
        return "planning"
    if feedback_type in {FeedbackType.REJECT.value, FeedbackType.NEW_TRIP.value}:
        return "greeting"

    # Safe fallback: continue planning loop.
    return "planning"


def normalize_feedback_type(value: Any) -> Optional[str]:
    """
    Normalize feedback type from enum/string payload into canonical lowercase value.
    """
    if value is None:
        return None

    if isinstance(value, FeedbackType):
        return value.value

    text = str(value).strip().lower()
    mapping = {
        FeedbackType.APPROVE.value: FeedbackType.APPROVE.value,
        FeedbackType.MODIFY.value: FeedbackType.MODIFY.value,
        FeedbackType.REJECT.value: FeedbackType.REJECT.value,
        FeedbackType.NEW_TRIP.value: FeedbackType.NEW_TRIP.value,
    }
    return mapping.get(text)


def _to_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "normalize_feedback_type",
    "route_after_constraint",
    "route_after_feedback",
    "route_after_greeting",
    "route_after_planning",
]
