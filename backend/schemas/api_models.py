"""
API models — FastAPI request/response schemas.

These wrap the core domain models for the REST API layer.
Used by:
  - FastAPI route handlers (backend/api/routes.py)
  - Frontend fetch calls (TypeScript types mirror these)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.itinerary import BudgetSummary, Itinerary
from backend.schemas.payment import BookingConfirmation
from backend.schemas.travel_state import FeedbackType, PlanningPhase


# ─── Request Models ──────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """
    User message sent to the /api/chat endpoint.

    Each message is associated with a thread for session continuity.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation thread ID (UUID). "
            "Omit or set to None to start a new conversation."
        ),
    )

    message: str = Field(
        ...,
        description="User's message text.",
        min_length=1,
        max_length=2000,
    )


class FeedbackRequest(BaseModel):
    """
    User feedback on a generated itinerary, sent to /api/feedback.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    thread_id: str = Field(
        ...,
        description="Conversation thread ID.",
    )

    feedback_type: FeedbackType = Field(
        ...,
        description="Type of feedback: approve, modify, reject, or new_trip.",
    )

    feedback_text: Optional[str] = Field(
        default=None,
        description=(
            "Optional detailed feedback. Required when feedback_type is 'modify'. "
            "e.g., 'Reduce hotel budget and add more street food spots.'"
        ),
        max_length=1000,
    )


class ConfirmRequest(BaseModel):
    """
    Booking confirmation request sent to /api/confirm.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    thread_id: str = Field(
        ...,
        description="Conversation thread ID.",
    )


# ─── Response Models ─────────────────────────────────────────────────


class ResponseStatus(str, Enum):
    """Status indicator for API responses."""

    SUCCESS = "success"
    AWAITING_INPUT = "awaiting_input"
    AWAITING_FEEDBACK = "awaiting_feedback"
    PROCESSING = "processing"
    ERROR = "error"
    COMPLETE = "complete"


class ChatResponse(BaseModel):
    """
    Response from the /api/chat endpoint.

    Contains the agent's reply, current phase, and optionally
    the generated itinerary if the system has reached that stage.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    thread_id: str = Field(
        ...,
        description="Conversation thread ID.",
    )

    response: str = Field(
        ...,
        description="Agent's text response to display in the chat.",
    )

    phase: PlanningPhase = Field(
        ...,
        description="Current workflow phase.",
    )

    status: ResponseStatus = Field(
        ...,
        description="Response status indicator.",
    )

    itinerary: Optional[Itinerary] = Field(
        default=None,
        description="Generated itinerary (present when phase is 'feedback' or later).",
    )

    budget_summary: Optional[BudgetSummary] = Field(
        default=None,
        description="Budget breakdown (present alongside itinerary).",
    )

    booking: Optional[BookingConfirmation] = Field(
        default=None,
        description="Booking confirmation (present when phase is 'complete').",
    )

    errors: list[str] = Field(
        default_factory=list,
        description="Any error messages from the current step.",
    )


class FeedbackResponse(BaseModel):
    """Response from the /api/feedback endpoint."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    thread_id: str = Field(
        ...,
        description="Conversation thread ID.",
    )

    status: ResponseStatus = Field(
        ...,
        description="Status after processing feedback.",
    )

    message: str = Field(
        ...,
        description="Confirmation message. e.g., 'Re-planning with updated preferences...'",
    )

    phase: PlanningPhase = Field(
        ...,
        description="Updated workflow phase after feedback.",
    )

    itinerary: Optional[Itinerary] = Field(
        default=None,
        description="Updated itinerary (if re-planning is complete in this response).",
    )


class HealthResponse(BaseModel):
    """Response from the /api/health endpoint."""

    status: str = Field(default="ok")
    version: str = Field(default="0.1.0")
    mcp_server: str = Field(
        default="unknown",
        description="MCP server connection status: 'connected' or 'disconnected'.",
    )


class ErrorResponse(BaseModel):
    """Standard error response for API errors."""

    error: str = Field(
        ...,
        description="Error message.",
    )

    detail: Optional[str] = Field(
        default=None,
        description="Additional error details for debugging.",
    )

    phase: Optional[PlanningPhase] = Field(
        default=None,
        description="Phase where the error occurred.",
    )
