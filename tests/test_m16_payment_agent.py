"""
Tests for Module M16: Payment Agent.

Validates:
- booking confirmation generation with UUID reference
- status confirmed and phase transition to complete
- summary fields include flight/hotel/total details
- clarification path when itinerary is missing
- wrapped error fallback path
"""

import asyncio
import inspect
import os
import sys
from uuid import UUID

sys.path.insert(0, os.path.abspath("."))

import backend.agents.payment_agent.agent as payment_module
from backend.agents.payment_agent.agent import payment_node
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, Itinerary
from backend.schemas.payment import BookingConfirmation, BookingStatus
from backend.schemas.transport import FlightOption


def _sample_state() -> dict:
    itinerary = Itinerary(
        title="Paris Discovery",
        destination="Paris, France",
        source_location="Mumbai, India",
        start_date="2026-06-01",
        end_date="2026-06-05",
        num_travelers=2,
        days=[],
        total_estimated_cost=1800.0,
        highlights=["Louvre Museum", "Seine Cruise"],
        warnings=[],
    )

    return {
        "travel_intent": {
            "destination": "Paris, France",
            "source_location": "Mumbai, India",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "num_travelers": 2,
            "budget": 3000.0,
            "currency": "USD",
        },
        "itinerary": itinerary,
        "budget_summary": BudgetSummary(
            transport_cost=900.0,
            accommodation_cost=720.0,
            activities_cost=80.0,
            food_estimate=240.0,
            miscellaneous=120.0,
            total=2060.0,
            budget_limit=3000.0,
            currency="USD",
        ),
        "flight_options": [
            FlightOption(
                airline="AF",
                flight_number="AF217",
                origin="BOM",
                destination="CDG",
                departure_time="2026-06-01T10:00:00",
                arrival_time="2026-06-01T18:00:00",
                duration="PT11H",
                price=900.0,
                currency="USD",
                stops=0,
            )
        ],
        "hotel_options": [
            HotelOption(
                name="Hotel Le Marais",
                hotel_id="H-001",
                address="Paris",
                city="Paris",
                rating=4.3,
                price_per_night=180.0,
                total_price=720.0,
                currency="USD",
                amenities=["WiFi", "Breakfast"],
            )
        ],
        "current_phase": "payment",
    }


async def test_m16_payment_agent():
    print("=" * 60)
    print("M16 Payment Agent Tests")
    print("=" * 60)

    # ── 1. Happy path confirmation generation ───────────────────────
    print("\n[1] Testing booking confirmation generation...")
    result = await payment_node(_sample_state())
    assert result["current_phase"] == "complete"
    assert isinstance(result.get("booking_confirmation"), BookingConfirmation)
    confirmation = result["booking_confirmation"]
    UUID(confirmation.booking_reference)  # raises if invalid UUID format
    assert confirmation.status == BookingStatus.CONFIRMED
    print("  OK: booking confirmation generated with UUID + confirmed status")

    # ── 2. Summary content checks ────────────────────────────────────
    print("\n[2] Testing summary content...")
    assert "BOM" in confirmation.flight_summary
    assert "Hotel Le Marais" in confirmation.hotel_summary
    assert confirmation.estimated_total_cost == 2060.0
    assert confirmation.currency == "USD"
    print("  OK: flight/hotel/total summaries are populated")

    # ── 3. Missing-itinerary clarification path ──────────────────────
    print("\n[3] Testing missing-itinerary clarification...")
    missing_state = _sample_state()
    missing_state["itinerary"] = None
    missing_result = await payment_node(missing_state)
    assert missing_result["current_phase"] == "feedback"
    assert "booking_confirmation" not in missing_result
    assert isinstance(missing_result.get("messages"), list)
    assert "itinerary" in missing_result["messages"][0].lower()
    print("  OK: missing itinerary returns clarification, not fake success")

    # ── 4. Error fallback wrapping ───────────────────────────────────
    print("\n[4] Testing wrapped error fallback path...")
    original_builder = payment_module.PaymentAgent._build_booking_confirmation

    def _boom(self, **_kwargs):
        raise RuntimeError("synthetic payment failure")

    payment_module.PaymentAgent._build_booking_confirmation = _boom
    try:
        failure_result = await payment_node(_sample_state())
    finally:
        payment_module.PaymentAgent._build_booking_confirmation = original_builder

    assert failure_result["current_phase"] == "feedback"
    assert isinstance(failure_result.get("errors"), list)
    assert "payment_agent failed during run" in failure_result["errors"][0]
    print("  OK: errors are wrapped and returned in fallback response")

    # ── 5. Ensure no MCP/http usage in payment agent ────────────────
    print("\n[5] Testing no MCP/http usage in payment agent...")
    source = inspect.getsource(__import__("backend.agents.payment_agent.agent", fromlist=["*"]))
    lowered = source.lower()
    assert "mcpclient" not in lowered
    assert "httpx" not in lowered
    print("  OK: payment agent has no MCP/http dependency")

    print("\n" + "=" * 60)
    print("✓ All M16 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m16_payment_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

