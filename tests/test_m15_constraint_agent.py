"""
Tests for Module M15: Constraint Agent.

Validates:
- itinerary assembly from gathered data
- budget summary computation and feedback phase transition
- partial itinerary generation with warnings when data is missing
- over-budget warning behavior
- wrapped error fallback path
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

import backend.agents.constraint_agent.agent as constraint_module
from backend.agents.constraint_agent.agent import constraint_node
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, InsightCategory, Itinerary, LocalInsight
from backend.schemas.transport import FlightOption


def _sample_state() -> dict:
    return {
        "travel_intent": {
            "destination": "Paris, France",
            "source_location": "Mumbai, India",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "num_travelers": 2,
            "budget": 5000.0,
            "currency": "USD",
        },
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
        "local_insights": [
            LocalInsight(
                name="Louvre Museum",
                category=InsightCategory.CULTURAL,
                description="Classic art museum visit.",
                location="Paris",
                estimated_cost=30.0,
                duration_hours=3.0,
                source_url="https://example.com/louvre",
                rating=4.8,
            ),
            LocalInsight(
                name="Seine River Cruise",
                category=InsightCategory.ACTIVITY,
                description="Evening cruise in central Paris.",
                location="Paris",
                estimated_cost=25.0,
                duration_hours=1.5,
                source_url="https://example.com/seine",
                rating=4.6,
            ),
        ],
        "current_phase": "itinerary",
    }


async def test_m15_constraint_agent():
    print("=" * 60)
    print("M15 Constraint Agent Tests")
    print("=" * 60)

    # ── 1. Happy path ───────────────────────────────────────────────
    print("\n[1] Testing full-data itinerary assembly...")
    full_state = _sample_state()
    full_result = await constraint_node(full_state)
    assert full_result["current_phase"] == "feedback"
    assert isinstance(full_result.get("itinerary"), Itinerary)
    assert isinstance(full_result.get("budget_summary"), BudgetSummary)
    assert full_result["itinerary"].destination == "Paris, France"
    assert len(full_result["itinerary"].days) > 0
    print("  OK: itinerary and budget summary are generated")

    # ── 2. Partial-data path (missing hotel options) ────────────────
    print("\n[2] Testing partial itinerary with missing source...")
    partial_state = _sample_state()
    partial_state["hotel_options"] = []
    partial_result = await constraint_node(partial_state)
    assert partial_result["current_phase"] == "feedback"
    assert isinstance(partial_result.get("itinerary"), Itinerary)
    warnings_text = " ".join(partial_result["itinerary"].warnings).lower()
    assert "hotel" in warnings_text
    print("  OK: partial itinerary is produced with warnings")

    # ── 3. Over-budget behavior ──────────────────────────────────────
    print("\n[3] Testing over-budget warning behavior...")
    budget_state = _sample_state()
    budget_state["travel_intent"]["budget"] = 100.0
    budget_result = await constraint_node(budget_state)
    assert budget_result["budget_summary"].within_budget is False
    assert any("budget" in w.lower() for w in budget_result["itinerary"].warnings)
    print("  OK: over-budget condition produces warning")

    # ── 4. Error fallback wrapping ───────────────────────────────────
    print("\n[4] Testing wrapped error fallback path...")
    original_compute = constraint_module._compute_budget_summary

    def _boom(**_kwargs):
        raise RuntimeError("synthetic constraint failure")

    constraint_module._compute_budget_summary = _boom
    try:
        failure_result = await constraint_node(_sample_state())
    finally:
        constraint_module._compute_budget_summary = original_compute

    assert failure_result["current_phase"] == "planning"
    assert isinstance(failure_result.get("errors"), list)
    assert "constraint_agent failed during run" in failure_result["errors"][0]
    print("  OK: failures are wrapped and returned in fallback response")

    # ── 5. Ensure no MCP/http usage in constraint node ──────────────
    print("\n[5] Testing no MCP/http usage in constraint agent...")
    source = inspect.getsource(
        __import__("backend.agents.constraint_agent.agent", fromlist=["*"])
    )
    lowered = source.lower()
    assert "mcpclient" not in lowered
    assert "httpx" not in lowered
    print("  OK: constraint agent does not call MCP tools directly")

    print("\n" + "=" * 60)
    print("✓ All M15 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m15_constraint_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

