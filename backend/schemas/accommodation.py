"""
Accommodation schemas — hotel search parameters and hotel option results.

Used by:
  - MCP Server tool `search_hotels` (HotelSearchInput as input)
  - Accommodation Agent (HotelOption as output into TravelState)
  - Constraint Agent (HotelOption as input for itinerary assembly)
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ─── Enums ───────────────────────────────────────────────────────────


class PriceRange(str, Enum):
    """Hotel price tier for filtering results."""

    BUDGET = "budget"
    MID = "mid"
    LUXURY = "luxury"


# ─── MCP Tool Input ──────────────────────────────────────────────────


class HotelSearchInput(BaseModel):
    """
    Input parameters for the `search_hotels` MCP tool.

    The Accommodation Agent constructs this from the TravelIntent,
    mapping the destination to an IATA city code and computing
    check-in / check-out dates.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    city_code: str = Field(
        ...,
        description="IATA city code for hotel search. e.g., 'PAR' for Paris.",
        min_length=3,
        max_length=3,
    )

    check_in: str = Field(
        ...,
        description="Check-in date in ISO format (YYYY-MM-DD).",
    )

    check_out: str = Field(
        ...,
        description="Check-out date in ISO format (YYYY-MM-DD).",
    )

    adults: int = Field(
        default=1,
        description="Number of adult guests.",
        ge=1,
        le=9,
    )

    max_results: int = Field(
        default=5,
        description="Maximum number of hotel options to return.",
        ge=1,
        le=20,
    )

    price_range: Optional[PriceRange] = Field(
        default=None,
        description="Filter by price tier: budget, mid, or luxury.",
    )

    currency: str = Field(
        default="USD",
        description="Price currency code (ISO 4217).",
        min_length=3,
        max_length=3,
    )

    # ── Validators ───────────────────────────────────────────────

    @field_validator("city_code")
    @classmethod
    def validate_city_code(cls, v: str) -> str:
        """City codes must be uppercase alphabetic."""
        v = v.upper()
        if not v.isalpha():
            raise ValueError(f"City code '{v}' must contain only letters.")
        return v

    @field_validator("check_in", "check_out")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
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
        return v.upper()

    @model_validator(mode="after")
    def validate_checkout_after_checkin(self) -> HotelSearchInput:
        """Check-out must be after check-in."""
        if self.check_in and self.check_out:
            ci = date.fromisoformat(self.check_in)
            co = date.fromisoformat(self.check_out)
            if co <= ci:
                raise ValueError("check_out must be after check_in.")
        return self


# ─── Data Output ─────────────────────────────────────────────────────


class HotelOption(BaseModel):
    """
    A single hotel search result returned by the MCP server.

    Represents one bookable hotel option with pricing and amenities.
    Used in TravelState.hotel_options and in DayPlan.hotel.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",  # Amadeus may return extra fields we want to preserve
    )

    name: str = Field(
        ...,
        description="Hotel name. e.g., 'Hotel Le Marais'.",
    )

    hotel_id: Optional[str] = Field(
        default=None,
        description="Unique hotel identifier from the data source.",
    )

    address: str = Field(
        default="",
        description="Full hotel address.",
    )

    city: Optional[str] = Field(
        default=None,
        description="City where the hotel is located.",
    )

    rating: float = Field(
        default=0.0,
        description="Hotel star rating (0-5 scale).",
        ge=0,
        le=5,
    )

    price_per_night: float = Field(
        ...,
        description="Price per night in the specified currency.",
        ge=0,
    )

    total_price: Optional[float] = Field(
        default=None,
        description="Total price for the entire stay (all nights).",
        ge=0,
    )

    currency: str = Field(
        default="USD",
        description="Price currency code.",
        min_length=3,
        max_length=3,
    )

    amenities: list[str] = Field(
        default_factory=list,
        description="List of amenities. e.g., ['WiFi', 'Pool', 'Breakfast'].",
    )

    source_url: Optional[str] = Field(
        default=None,
        description="URL to the hotel listing for more details.",
    )

    image_url: Optional[str] = Field(
        default=None,
        description="URL to a hotel photo (if available).",
    )
