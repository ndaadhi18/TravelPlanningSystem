"""
Tests for Module M12: Transport Agent.

Validates:
- intent -> FlightSearchInput mapping
- clarification path for missing fields
- MCP failure fallback behavior
- agent uses MCPClient abstraction (no direct HTTP calls)
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.agents.transport_agent.agent import transport_node
from backend.schemas.transport import FlightOption
from backend.services.mcp_client import MCPClientError


class _FakeMCPClientSuccess:
    def __init__(self):
        self.called_with = None
        self.call_count = 0

    async def search_flights(self, params):
        self.called_with = params
        self.call_count += 1
        return [
            FlightOption(
                airline="AF",
                flight_number="AF217",
                origin="BOM",
                destination="CDG",
                departure_time="2026-06-01T10:00:00",
                arrival_time="2026-06-01T18:30:00",
                duration="PT11H",
                price=850.0,
                currency="USD",
                stops=0,
            )
        ]

    async def close(self):
        return None


class _FakeMCPClientFailure:
    async def search_flights(self, _params):
        raise MCPClientError("synthetic MCP failure")

    async def close(self):
        return None


async def test_m12_transport_agent():
    print("=" * 60)
    print("M12 Transport Agent Tests")
    print("=" * 60)

    # ── 1. Happy path: map intent and fetch flights ──────────────────
    print("\n[1] Testing intent to flight search mapping...")
    success_client = _FakeMCPClientSuccess()
    state = {
        "travel_intent": {
            "source_location": "Mumbai, India",
            "destination": "Paris, France",
            "start_date": "2026-06-01",
            "end_date": "2026-06-08",
            "num_travelers": 2,
            "currency": "USD",
        },
        "current_phase": "planning",
    }

    result = await transport_node(state, mcp_client=success_client)
    assert isinstance(result.get("flight_options"), list)
    assert len(result["flight_options"]) == 1
    assert success_client.call_count == 1
    assert success_client.called_with.origin == "BOM"
    assert success_client.called_with.destination == "CDG"
    assert success_client.called_with.departure_date == "2026-06-01"
    assert success_client.called_with.return_date == "2026-06-08"
    assert success_client.called_with.adults == 2
    print("  OK: transport agent maps intent and calls MCP client")

    # ── 2. Clarification path for missing fields ─────────────────────
    print("\n[2] Testing missing-field clarification...")
    incomplete_state = {
        "travel_intent": {
            "destination": "Paris, France",
        },
        "current_phase": "planning",
    }
    incomplete_result = await transport_node(incomplete_state, mcp_client=success_client)
    assert incomplete_result["current_phase"] == "planning"
    assert incomplete_result["flight_options"] == []
    assert isinstance(incomplete_result.get("messages"), list)
    clarification = incomplete_result["messages"][0].lower()
    assert ("departure city" in clarification) or ("departure date" in clarification)
    print("  OK: missing fields return clarification response")

    # ── 3. MCP failure fallback behavior ──────────────────────────────
    print("\n[3] Testing MCP failure fallback...")
    failing_state = {
        "travel_intent": {
            "source_location": "BOM",
            "destination": "CDG",
            "start_date": "2026-06-01",
        },
        "current_phase": "planning",
    }
    failing_result = await transport_node(failing_state, mcp_client=_FakeMCPClientFailure())
    assert failing_result["flight_options"] == []
    assert isinstance(failing_result.get("errors"), list)
    assert len(failing_result["errors"]) == 1
    assert "transport_agent failed during run" in failing_result["errors"][0]
    print("  OK: MCP errors are wrapped with safe fallback response")

    # ── 4. Ensure no direct HTTP client usage in transport node ──────
    print("\n[4] Testing no direct HTTP usage in transport agent...")
    module = __import__("backend.agents.transport_agent.agent", fromlist=["*"])
    source = inspect.getsource(module)
    assert "httpx" not in source.lower()
    assert "MCPClient" in source
    print("  OK: transport agent depends on MCPClient abstraction only")

    print("\n" + "=" * 60)
    print("✓ All M12 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m12_transport_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

