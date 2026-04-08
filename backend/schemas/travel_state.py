"""
TravelState — the Pydantic representation of the LangGraph shared state.

This module defines a *serializable* Pydantic model that mirrors the
LangGraph TypedDict state. It is used for:
  - API responses (serialising current state to JSON for the frontend)
  - Snapshot persistence / debugging
  - Type-safe access outside of graph execution

The actual LangGraph TypedDict (with Annotated reducers) lives in
`backend.orchestration.state` (Module M17). That TypedDict uses the
Pydantic models defined here for its typed fields.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, Itinerary, LocalInsight
from backend.schemas.payment import BookingConfirmation
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent


# ─── Enums ───────────────────────────────────────────────────────────


class PlanningPhase(str, Enum):
    """
    Tracks which phase the planning workflow is currently in.

    Used by the Planning Agent for routing decisions and by the
    frontend to render the appropriate UI state.
    """

    GREETING = "greeting"
    PLANNING = "planning"
    DATA_GATHERING = "data_gathering"
    ITINERARY = "itinerary"
    FEEDBACK = "feedback"
    PAYMENT = "payment"
    COMPLETE = "complete"
    ERROR = "error"


class FeedbackType(str, Enum):
    """Types of user feedback on a generated itinerary."""

    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"
    NEW_TRIP = "new_trip"


# ─── Travel State (Pydantic) ────────────────────────────────────────


class TravelStateSummary(BaseModel):
    """
    Serialisable snapshot of the full planning state.

    This is NOT the LangGraph TypedDict — it is a Pydantic model
    for API serialisation and state inspection. The actual graph
    state (with `Annotated` reducers) is defined in
    `backend.orchestration.state.TravelState`.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    # ── User intent ──────────────────────────────────────────────

    travel_intent: Optional[TravelIntent] = Field(
        default=None,
        description="Structured travel intent extracted from user conversation.",
    )

    intent_confirmed: bool = Field(
        default=False,
        description="Whether the user has confirmed the extracted intent.",
    )

    # ── Gathered data ────────────────────────────────────────────

    flight_options: list[FlightOption] = Field(
        default_factory=list,
        description="Flight options returned by the Transport Agent.",
    )

    hotel_options: list[HotelOption] = Field(
        default_factory=list,
        description="Hotel options returned by the Accommodation Agent.",
    )

    local_insights: list[LocalInsight] = Field(
        default_factory=list,
        description="Local attractions / activities from the Local Expert Agent.",
    )

    # ── Itinerary ────────────────────────────────────────────────

    itinerary: Optional[Itinerary] = Field(
        default=None,
        description="The assembled day-by-day itinerary.",
    )

    budget_summary: Optional[BudgetSummary] = Field(
        default=None,
        description="Cost breakdown for the itinerary.",
    )

    # ── Feedback loop ────────────────────────────────────────────

    feedback: Optional[str] = Field(
        default=None,
        description="User's feedback text on the current itinerary.",
    )

    feedback_type: Optional[FeedbackType] = Field(
        default=None,
        description="Type of feedback: approve, modify, reject, or new_trip.",
    )

    iteration_count: int = Field(
        default=0,
        description="Number of feedback iterations so far (max 10).",
        ge=0,
        le=10,
    )

    # ── Booking ──────────────────────────────────────────────────

    booking_confirmation: Optional[BookingConfirmation] = Field(
        default=None,
        description="Simulated booking confirmation (after user approval).",
    )

    # ── Workflow metadata ────────────────────────────────────────

    current_phase: PlanningPhase = Field(
        default=PlanningPhase.GREETING,
        description="Current phase of the planning workflow.",
    )

    errors: list[str] = Field(
        default_factory=list,
        description="Accumulated error messages from agent execution.",
    )
