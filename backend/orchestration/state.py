"""
LangGraph state definitions for PLANIT orchestration.

M17 scope:
- Define the shared TravelState TypedDict used across graph nodes
- Apply reducer annotations for LangGraph merge behavior
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, Itinerary, LocalInsight
from backend.schemas.payment import BookingConfirmation
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent
from backend.schemas.travel_state import FeedbackType, PlanningPhase


class TravelState(TypedDict, total=False):
    """
    Shared LangGraph state.

    Only `messages` and `errors` use additive reducers. All other fields follow
    overwrite semantics on node updates.
    """

    # Conversation
    messages: Annotated[list[AnyMessage], add_messages]

    # Intent extraction
    travel_intent: Optional[TravelIntent]
    intent_confirmed: bool

    # Gathered data
    flight_options: list[FlightOption]
    hotel_options: list[HotelOption]
    local_insights: list[LocalInsight]

    # Itinerary and budgeting
    itinerary: Optional[Itinerary]
    budget_summary: Optional[BudgetSummary]

    # Feedback loop
    feedback: Optional[str]
    feedback_type: Optional[FeedbackType]
    iteration_count: int

    # Payment outcome
    booking_confirmation: Optional[BookingConfirmation]

    # Workflow metadata
    current_phase: PlanningPhase
    errors: Annotated[list[str], operator.add]


def create_initial_state(*, messages: Optional[list[AnyMessage]] = None) -> TravelState:
    """
    Create a safe initial graph state.
    """
    return TravelState(
        messages=list(messages or []),
        travel_intent=None,
        intent_confirmed=False,
        flight_options=[],
        hotel_options=[],
        local_insights=[],
        itinerary=None,
        budget_summary=None,
        feedback=None,
        feedback_type=None,
        iteration_count=0,
        booking_confirmation=None,
        current_phase=PlanningPhase.GREETING,
        errors=[],
    )


__all__ = [
    "TravelState",
    "create_initial_state",
]
