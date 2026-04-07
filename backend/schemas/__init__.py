"""
PlanIT Schemas — all Pydantic data models for the travel planning system.

Re-exports every model for convenient imports:
    from backend.schemas import TravelIntent, FlightOption, Itinerary
"""

# ── Travel Intent ────────────────────────────────────────────────────
from backend.schemas.travel_intent import TravelIntent, TravelStyle

# ── Transport ────────────────────────────────────────────────────────
from backend.schemas.transport import FlightOption, FlightSearchInput

# ── Accommodation ────────────────────────────────────────────────────
from backend.schemas.accommodation import HotelOption, HotelSearchInput, PriceRange

# ── Itinerary & Local Insights ───────────────────────────────────────
from backend.schemas.itinerary import (
    BudgetSummary,
    DayPlan,
    InsightCategory,
    Itinerary,
    LocalInsight,
    SearchDepth,
    WebSearchInput,
)

# ── Payment ──────────────────────────────────────────────────────────
from backend.schemas.payment import BookingConfirmation, BookingStatus

# ── Travel State ─────────────────────────────────────────────────────
from backend.schemas.travel_state import (
    FeedbackType,
    PlanningPhase,
    TravelStateSummary,
)

# ── API Models ───────────────────────────────────────────────────────
from backend.schemas.api_models import (
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    ResponseStatus,
)

__all__ = [
    # Travel Intent
    "TravelIntent",
    "TravelStyle",
    # Transport
    "FlightSearchInput",
    "FlightOption",
    # Accommodation
    "HotelSearchInput",
    "HotelOption",
    "PriceRange",
    # Itinerary
    "WebSearchInput",
    "SearchDepth",
    "LocalInsight",
    "InsightCategory",
    "DayPlan",
    "Itinerary",
    "BudgetSummary",
    # Payment
    "BookingConfirmation",
    "BookingStatus",
    # Travel State
    "TravelStateSummary",
    "PlanningPhase",
    "FeedbackType",
    # API Models
    "ChatRequest",
    "ChatResponse",
    "FeedbackRequest",
    "FeedbackResponse",
    "ConfirmRequest",
    "HealthResponse",
    "ErrorResponse",
    "ResponseStatus",
]
