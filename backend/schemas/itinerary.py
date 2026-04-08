"""
Itinerary schemas — local insights, day plans, full itinerary, and budget summary.

Also includes WebSearchInput for the `web_search_places` MCP tool.

Used by:
  - MCP Server tool `web_search_places` (WebSearchInput as input)
  - Local Expert Agent (LocalInsight as output)
  - Constraint Agent (assembles DayPlan, Itinerary, BudgetSummary)
  - Frontend (renders the full itinerary)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.accommodation import HotelOption
from backend.schemas.transport import FlightOption


# ─── MCP Tool Input ──────────────────────────────────────────────────


class SearchDepth(str, Enum):
    """Tavily search depth levels."""

    BASIC = "basic"
    ADVANCED = "advanced"


class WebSearchInput(BaseModel):
    """
    Input parameters for the `web_search_places` MCP tool.

    The Local Expert Agent constructs this from the TravelIntent,
    building targeted queries for attractions, food, and hidden gems.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    query: str = Field(
        ...,
        description=(
            "Search query for discovering local attractions and places. "
            "e.g., 'hidden gems in Paris for food lovers'"
        ),
        min_length=3,
        max_length=500,
    )

    search_depth: SearchDepth = Field(
        default=SearchDepth.BASIC,
        description="Search depth: 'basic' for fast results, 'advanced' for deeper.",
    )

    max_results: int = Field(
        default=5,
        description="Maximum number of results to return.",
        ge=1,
        le=20,
    )

    include_domains: Optional[list[str]] = Field(
        default=None,
        description=(
            "Prioritise results from these domains. "
            "e.g., ['tripadvisor.com', 'lonelyplanet.com']"
        ),
    )


# ─── Local Insight ───────────────────────────────────────────────────


class InsightCategory(str, Enum):
    """Categories for discovered local attractions and activities."""

    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    ACTIVITY = "activity"
    HIDDEN_GEM = "hidden_gem"
    CULTURAL = "cultural"
    NIGHTLIFE = "nightlife"
    SHOPPING = "shopping"
    NATURE = "nature"


class LocalInsight(BaseModel):
    """
    A single local attraction / activity discovered by the Local Expert Agent.

    Represents a place, experience, or recommendation for the destination.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",
    )

    name: str = Field(
        ...,
        description="Name of the place or activity. e.g., 'Le Marais Walking Tour'.",
    )

    category: InsightCategory = Field(
        ...,
        description="Type of insight: attraction, restaurant, activity, etc.",
    )

    description: str = Field(
        ...,
        description="Brief description of why this place is recommended.",
        max_length=1000,
    )

    location: Optional[str] = Field(
        default=None,
        description="Specific location / neighbourhood within the destination.",
    )

    estimated_cost: Optional[float] = Field(
        default=None,
        description="Estimated cost per person in local or trip currency.",
        ge=0,
    )

    duration_hours: Optional[float] = Field(
        default=None,
        description="Estimated time to spend at this place (in hours).",
        ge=0,
    )

    source_url: Optional[str] = Field(
        default=None,
        description="Source URL where this information was found.",
    )

    rating: Optional[float] = Field(
        default=None,
        description="Rating from source (if available), 0-5 scale.",
        ge=0,
        le=5,
    )


# ─── Day Plan ────────────────────────────────────────────────────────


class DayPlan(BaseModel):
    """
    Plan for a single day within the itinerary.

    Combines transport, accommodation, and activities into
    a coherent daily schedule.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    day_number: int = Field(
        ...,
        description="Day number in the trip (1-indexed).",
        ge=1,
    )

    date: str = Field(
        ...,
        description="Date for this day in ISO format (YYYY-MM-DD).",
    )

    title: Optional[str] = Field(
        default=None,
        description="Optional day title. e.g., 'Arrival & Montmartre Exploration'.",
    )

    activities: list[LocalInsight] = Field(
        default_factory=list,
        description="List of planned activities and places for this day.",
    )

    transport: Optional[FlightOption] = Field(
        default=None,
        description="Flight for this day (typically day 1 or last day).",
    )

    hotel: Optional[HotelOption] = Field(
        default=None,
        description="Hotel for the night (may be the same across multiple days).",
    )

    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or tips for this day.",
        max_length=500,
    )

    estimated_day_cost: float = Field(
        default=0.0,
        description="Estimated total cost for this day (activities + meals + local transport).",
        ge=0,
    )


# ─── Budget Summary ─────────────────────────────────────────────────


class BudgetSummary(BaseModel):
    """
    Breakdown of the estimated trip costs by category.

    Generated by the Constraint Agent after assembling the itinerary.
    Compared against the user's stated budget.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    transport_cost: float = Field(
        default=0.0,
        description="Total transport (flights) cost.",
        ge=0,
    )

    accommodation_cost: float = Field(
        default=0.0,
        description="Total accommodation (hotels) cost.",
        ge=0,
    )

    activities_cost: float = Field(
        default=0.0,
        description="Total estimated cost for planned activities.",
        ge=0,
    )

    food_estimate: float = Field(
        default=0.0,
        description="Estimated food and dining costs for the trip.",
        ge=0,
    )

    miscellaneous: float = Field(
        default=0.0,
        description="Buffer for local transport, tips, souvenirs, etc.",
        ge=0,
    )

    total: float = Field(
        default=0.0,
        description="Grand total of all estimated costs.",
        ge=0,
    )

    budget_limit: float = Field(
        default=0.0,
        description="User's stated budget (from TravelIntent).",
        ge=0,
    )

    currency: str = Field(
        default="USD",
        description="Currency for all amounts.",
    )

    within_budget: bool = Field(
        default=True,
        description="Whether the total fits within the user's budget.",
    )

    @model_validator(mode="after")
    def compute_within_budget(self) -> BudgetSummary:
        """Auto-compute within_budget based on total and budget_limit."""
        if self.total > 0 and self.budget_limit > 0:
            # Use object.__setattr__ to set without triggering validation
            object.__setattr__(self, "within_budget", self.total <= self.budget_limit)
        return self


# ─── Full Itinerary ──────────────────────────────────────────────────


class Itinerary(BaseModel):
    """
    The complete travel itinerary — the primary output of the system.

    Assembled by the Constraint Agent from flights, hotels, and
    local insights. Presented to the user for feedback.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    title: str = Field(
        ...,
        description="Itinerary title. e.g., '7 Days in Paris — Art & Culture'.",
    )

    destination: str = Field(
        ...,
        description="Primary destination.",
    )

    source_location: Optional[str] = Field(
        default=None,
        description="Origin city (if applicable).",
    )

    start_date: str = Field(
        ...,
        description="Trip start date (YYYY-MM-DD).",
    )

    end_date: str = Field(
        ...,
        description="Trip end date (YYYY-MM-DD).",
    )

    num_travelers: int = Field(
        default=1,
        description="Number of travelers.",
        ge=1,
    )

    days: list[DayPlan] = Field(
        default_factory=list,
        description="Ordered list of day-by-day plans.",
    )

    budget_summary: Optional[BudgetSummary] = Field(
        default=None,
        description="Full cost breakdown.",
    )

    total_estimated_cost: float = Field(
        default=0.0,
        description="Grand total estimated cost for the entire trip.",
        ge=0,
    )

    highlights: list[str] = Field(
        default_factory=list,
        description="Key highlights of the trip. e.g., ['Eiffel Tower at sunset', 'Seine River cruise'].",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings (over budget, tight schedule, etc.).",
    )
