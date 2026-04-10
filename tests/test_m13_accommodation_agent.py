"""
Tests for Module M13: Accommodation Agent.

Validates:
- intent -> HotelSearchInput mapping
- check_out derivation from duration_days
- clarification path for missing fields
- MCP failure fallback behavior
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.agents.accommodation_agent.agent import accommodation_node
from backend.schemas.accommodation import HotelOption, PriceRange
from backend.services.mcp_client import MCPClientError


class _FakeMCPClientSuccess:
    def __init__(self):
        self.called_with = None
        self.call_count = 0

    async def search_hotels(self, params):
        self.called_with = params
        self.call_count += 1
        return [
            HotelOption(
                name="Hotel Le Marais",
                hotel_id="H-001",
                address="Paris",
                city="Paris",
                rating=4.2,
                price_per_night=180.0,
                total_price=720.0,
                currency="USD",
                amenities=["WiFi"],
            )
        ]

    async def close(self):
        return None


class _FakeMCPClientFailure:
    async def search_hotels(self, _params):
        raise MCPClientError("synthetic MCP failure")

    async def close(self):
        return None


async def test_m13_accommodation_agent():
    print("=" * 60)
    print("M13 Accommodation Agent Tests")
    print("=" * 60)

    # ── 1. Happy path: map intent and fetch hotels ───────────────────
    print("\n[1] Testing intent to hotel search mapping...")
    success_client = _FakeMCPClientSuccess()
    state = {
        "travel_intent": {
            "destination": "Paris, France",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "num_travelers": 2,
            "travel_style": "mid-range",
            "currency": "USD",
            "budget": 2500,
        },
        "current_phase": "planning",
    }

    result = await accommodation_node(state, mcp_client=success_client)
    assert isinstance(result.get("hotel_options"), list)
    assert len(result["hotel_options"]) == 1
    assert success_client.call_count == 1
    assert success_client.called_with.city_code == "PAR"
    assert success_client.called_with.check_in == "2026-06-01"
    assert success_client.called_with.check_out == "2026-06-05"
    assert success_client.called_with.adults == 2
    assert success_client.called_with.price_range == PriceRange.MID
    print("  OK: accommodation agent maps intent and calls MCP client")

    # ── 2. Auto-compute check_out from duration_days ─────────────────
    print("\n[2] Testing check_out derivation from duration_days...")
    duration_state = {
        "travel_intent": {
            "destination": "Paris, France",
            "start_date": "2026-07-01",
            "duration_days": 4,
            "num_travelers": 1,
            "currency": "USD",
            "budget": 600,
        },
        "current_phase": "planning",
    }
    duration_result = await accommodation_node(duration_state, mcp_client=success_client)
    assert len(duration_result["hotel_options"]) == 1
    assert success_client.called_with.check_in == "2026-07-01"
    assert success_client.called_with.check_out == "2026-07-05"
    print("  OK: check_out is auto-computed from duration_days")

    # ── 3. Clarification path for missing fields ─────────────────────
    print("\n[3] Testing missing-field clarification...")
    incomplete_state = {
        "travel_intent": {
            "start_date": "2026-08-01",
        },
        "current_phase": "planning",
    }
    incomplete_result = await accommodation_node(incomplete_state, mcp_client=success_client)
    assert incomplete_result["current_phase"] == "planning"
    assert incomplete_result["hotel_options"] == []
    assert isinstance(incomplete_result.get("messages"), list)
    clarification = incomplete_result["messages"][0].lower()
    assert "destination" in clarification
    print("  OK: missing fields return clarification response")

    # ── 4. MCP failure fallback behavior ──────────────────────────────
    print("\n[4] Testing MCP failure fallback...")
    failing_state = {
        "travel_intent": {
            "destination": "PAR",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "num_travelers": 1,
        },
        "current_phase": "planning",
    }
    failing_result = await accommodation_node(failing_state, mcp_client=_FakeMCPClientFailure())
    assert failing_result["hotel_options"] == []
    assert isinstance(failing_result.get("errors"), list)
    assert len(failing_result["errors"]) == 1
    assert "accommodation_agent failed during run" in failing_result["errors"][0]
    print("  OK: MCP errors are wrapped with safe fallback response")

    # ── 5. Ensure no direct HTTP client usage in accommodation node ──
    print("\n[5] Testing no direct HTTP usage in accommodation agent...")
    module = __import__("backend.agents.accommodation_agent.agent", fromlist=["*"])
    source = inspect.getsource(module)
    assert "httpx" not in source.lower()
    assert "MCPClient" in source
    print("  OK: accommodation agent depends on MCPClient abstraction only")

    print("\n" + "=" * 60)
    print("✓ All M13 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m13_accommodation_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

