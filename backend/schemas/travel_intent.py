"""
TravelIntent — the structured representation of a user's travel request.

Extracted by the Greeting Agent from natural language input.
This is the entry point for the entire planning pipeline.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TravelStyle(str, Enum):
    """Supported travel style tiers that affect accommodation and activity selection."""

    BUDGET = "budget"
    MID_RANGE = "mid-range"
    LUXURY = "luxury"


class TravelIntent(BaseModel):
    """
    Structured user travel intent extracted from conversation.

    The Greeting Agent parses free-form user messages into this model.
    Fields are intentionally lenient (many Optional) because the agent
    may need multiple conversation turns to collect everything.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "destination": "Paris, France",
                    "source_location": "Mumbai, India",
                    "start_date": "2025-06-15",
                    "end_date": "2025-06-22",
                    "num_travelers": 2,
                    "budget": 3000.0,
                    "currency": "USD",
                    "preferences": "art museums, local cuisine, romantic spots",
                    "travel_style": "mid-range",
                }
            ]
        },
    )

    # ── Core fields ──────────────────────────────────────────────────

    destination: str = Field(
        ...,
        description="Target destination city/country. e.g., 'Paris, France'",
        min_length=2,
        max_length=200,
    )

    source_location: Optional[str] = Field(
        default=None,
        description="Origin city/country for departure. e.g., 'Mumbai, India'",
        max_length=200,
    )

    # ── Date fields ──────────────────────────────────────────────────

    start_date: Optional[str] = Field(
        default=None,
        description="Trip start date in ISO format (YYYY-MM-DD). e.g., '2025-06-15'",
    )

    end_date: Optional[str] = Field(
        default=None,
        description="Trip end date in ISO format (YYYY-MM-DD). e.g., '2025-06-22'",
    )

    duration_days: Optional[int] = Field(
        default=None,
        description="Trip duration in days. Alternative to specifying end_date.",
        ge=1,
        le=90,
    )

    # ── Traveler & budget ────────────────────────────────────────────

    num_travelers: int = Field(
        default=1,
        description="Number of travelers in the group.",
        ge=1,
        le=20,
    )

    budget: float = Field(
        ...,
        description="Total trip budget. Interpreted in the specified currency.",
        gt=0,
    )

    currency: str = Field(
        default="USD",
        description="Budget currency code (ISO 4217). e.g., 'USD', 'EUR', 'INR'",
        min_length=3,
        max_length=3,
    )

    # ── Preferences ──────────────────────────────────────────────────

    preferences: Optional[str] = Field(
        default=None,
        description=(
            "Free-text travel preferences. "
            "e.g., 'adventure, local food, off-the-beaten-path'"
        ),
        max_length=500,
    )

    travel_style: Optional[TravelStyle] = Field(
        default=None,
        description="Overall travel style: budget, mid-range, or luxury.",
    )

    special_requirements: Optional[str] = Field(
        default=None,
        description=(
            "Special needs: dietary restrictions, accessibility, "
            "medical, visa concerns, etc."
        ),
        max_length=500,
    )

    # ── Validators ───────────────────────────────────────────────────

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Ensure dates are valid ISO format if provided."""
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(
                f"Date '{v}' is not valid ISO format. Expected YYYY-MM-DD."
            )
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency_uppercase(cls, v: str) -> str:
        """Normalise currency to uppercase."""
        return v.upper()

    @model_validator(mode="after")
    def validate_date_logic(self) -> TravelIntent:
        """Cross-field validation for date consistency."""
        if self.start_date and self.end_date:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
            if end <= start:
                raise ValueError("end_date must be after start_date.")

            # Auto-fill duration_days if both dates are provided
            if self.duration_days is None:
                self.duration_days = (end - start).days

        return self

    # ── Helpers ───────────────────────────────────────────────────────

    def is_complete(self) -> bool:
        """
        Check whether the intent has enough information to proceed
        to the planning phase. Minimum: destination, budget, and
        either dates or duration.
        """
        has_dates = bool(self.start_date) or bool(self.duration_days)
        return bool(self.destination) and self.budget > 0 and has_dates
