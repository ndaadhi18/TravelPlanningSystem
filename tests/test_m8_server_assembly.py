"""
Tests for Module M8: MCP Server Assembly.

Validates that the server registers all three tool wrappers and supports
both stdio and streamable HTTP startup modes.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.mcp_servers import server as mcp_server
from backend.schemas.accommodation import HotelSearchInput
from backend.schemas.itinerary import WebSearchInput
from backend.schemas.transport import FlightSearchInput


async def test_m8_server_assembly():
    print("=" * 60)
    print("M8 MCP Server Assembly Tests")
    print("=" * 60)

    # ── 1. Server and tool wrappers exist ──────────────────────────────
    print("\n[1] Checking server bootstrap and tool wrappers...")
    assert mcp_server.mcp is not None
    assert callable(mcp_server.search_flights)
    assert callable(mcp_server.search_hotels)
    assert callable(mcp_server.web_search_places)
    print("  OK: FastMCP server and all 3 tool wrappers are defined")

    # ── 2. Wrapper delegation for all tools ─────────────────────────────
    print("\n[2] Verifying wrapper delegation to tool functions...")
    original_flights_tool = mcp_server.search_flights_tool
    original_hotels_tool = mcp_server.search_hotels_tool
    original_places_tool = mcp_server.web_search_places_tool

    try:
        async def fake_flights_tool(_params: FlightSearchInput):
            return [{"tool": "flights", "ok": True}]

        async def fake_hotels_tool(_params: HotelSearchInput):
            return [{"tool": "hotels", "ok": True}]

        async def fake_places_tool(_params: WebSearchInput):
            return [{"tool": "places", "ok": True}]

        mcp_server.search_flights_tool = fake_flights_tool
        mcp_server.search_hotels_tool = fake_hotels_tool
        mcp_server.web_search_places_tool = fake_places_tool

        flights_result = await mcp_server.search_flights(
            FlightSearchInput(
                origin="BOM",
                destination="CDG",
                departure_date="2025-06-15",
                adults=1,
            )
        )
        hotels_result = await mcp_server.search_hotels(
            HotelSearchInput(
                city_code="PAR",
                check_in="2025-06-15",
                check_out="2025-06-22",
                adults=1,
            )
        )
        places_result = await mcp_server.web_search_places(
            WebSearchInput(
                query="hidden gems in Paris",
                max_results=3,
            )
        )

        assert flights_result[0]["tool"] == "flights"
        assert hotels_result[0]["tool"] == "hotels"
        assert places_result[0]["tool"] == "places"
        print("  OK: All wrappers delegate correctly")
    finally:
        mcp_server.search_flights_tool = original_flights_tool
        mcp_server.search_hotels_tool = original_hotels_tool
        mcp_server.web_search_places_tool = original_places_tool

    # ── 3. Startup mode handling ────────────────────────────────────────
    print("\n[3] Verifying stdio + streamable HTTP startup modes...")
    original_run = mcp_server.mcp.run
    calls = []

    try:
        def fake_run(transport=None, host=None, port=None):
            calls.append(
                {
                    "transport": transport,
                    "host": host,
                    "port": port,
                }
            )

        mcp_server.mcp.run = fake_run
        mcp_server.run_server("stdio")
        mcp_server.run_server("streamable-http")

        assert len(calls) == 2
        assert calls[0]["transport"] is None  # stdio mode calls mcp.run()
        assert calls[1]["transport"] == "streamable-http"
        print(
            "  OK: startup supports both modes "
            f"(host={calls[1]['host']}, port={calls[1]['port']})"
        )
    finally:
        mcp_server.mcp.run = original_run

    # ── 4. Invalid mode rejection ───────────────────────────────────────
    print("\n[4] Verifying invalid startup mode rejection...")
    try:
        mcp_server.run_server("invalid-mode")
        print("  FAIL: invalid mode should raise ValueError")
        sys.exit(1)
    except ValueError:
        print("  OK: Invalid mode rejected")

    print("\n" + "=" * 60)
    print("✓ All M8 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_m8_server_assembly())
