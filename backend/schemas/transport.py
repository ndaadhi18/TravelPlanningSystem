"""
Transport schemas — flight search parameters and flight option results.

Used by:
  - MCP Server tool `search_flights` (FlightSearchInput as input)
  - Transport Agent (FlightOption as output into TravelState)
  - Constraint Agent (FlightOption as input for itinerary assembly)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── MCP Tool Input ──────────────────────────────────────────────────


class FlightSearchInput(BaseModel):
    """
    Input parameters for the `search_flights` MCP tool.

    The Transport Agent constructs this from the TravelIntent,
    mapping city names to IATA codes and formatting dates.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    origin: str = Field(
        ...,
        description="Origin airport IATA code. e.g., 'BOM' for Mumbai.",
        min_length=3,
        max_length=3,
    )

    destination: str = Field(
        ...,
        description="Destination airport IATA code. e.g., 'CDG' for Paris.",
        min_length=3,
        max_length=3,
    )

    departure_date: str = Field(
        ...,
        description="Departure date in ISO format (YYYY-MM-DD).",
    )

    return_date: Optional[str] = Field(
        default=None,
        description="Return date in ISO format. None for one-way trips.",
    )

    adults: int = Field(
        default=1,
        description="Number of adult passengers.",
        ge=1,
        le=9,
    )

    max_results: int = Field(
        default=5,
        description="Maximum number of flight options to return.",
        ge=1,
        le=20,
    )

    currency: str = Field(
        default="USD",
        description="Price currency code (ISO 4217).",
        min_length=3,
        max_length=3,
    )

    # ── Validators ───────────────────────────────────────────────

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata_code(cls, v: str) -> str:
        """IATA codes must be uppercase alphabetic."""
        v = v.upper()
        if not v.isalpha():
            raise ValueError(f"IATA code '{v}' must contain only letters.")
        return v

    @field_validator("departure_date", "return_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
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
        return v.upper()


# ─── Data Output ─────────────────────────────────────────────────────


class FlightOption(BaseModel):
    """
    A single flight search result returned by the MCP server.

    Represents one bookable flight offer with pricing.
    Used in TravelState.flight_options and in DayPlan.transport.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",  # Amadeus may return extra fields we want to preserve
    )

    airline: str = Field(
        ...,
        description="Airline name or IATA carrier code. e.g., 'Air France' or 'AF'.",
    )

    flight_number: str = Field(
        ...,
        description="Flight number. e.g., 'AF 218'.",
    )

    origin: str = Field(
        ...,
        description="Departure airport IATA code.",
        min_length=3,
        max_length=3,
    )

    destination: str = Field(
        ...,
        description="Arrival airport IATA code.",
        min_length=3,
        max_length=3,
    )

    departure_time: str = Field(
        ...,
        description="Departure datetime in ISO 8601 format.",
    )

    arrival_time: str = Field(
        ...,
        description="Arrival datetime in ISO 8601 format.",
    )

    duration: str = Field(
        ...,
        description="Total flight duration. e.g., 'PT8H30M' or '8h 30m'.",
    )

    price: float = Field(
        ...,
        description="Total price for this flight option.",
        ge=0,
    )

    currency: str = Field(
        default="USD",
        description="Price currency code.",
        min_length=3,
        max_length=3,
    )

    stops: int = Field(
        default=0,
        description="Number of intermediate stops. 0 = direct flight.",
        ge=0,
    )

    cabin_class: Optional[str] = Field(
        default=None,
        description="Cabin class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST.",
    )

    booking_url: Optional[str] = Field(
        default=None,
        description="Deep-link URL for booking (if available).",
    )
