"""
Tests for Module M5: MCP Tool — search_flights.

Validates that the search_flights_tool correctly calls the AmadeusClient
and parses the raw response into FlightOption Pydantic models.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from backend.mcp_servers.tools.search_flights import search_flights_tool
from backend.schemas.transport import FlightSearchInput, FlightOption


async def test_search_flights_mock_parsing():
    print("=" * 60)
    print("M5 search_flights MCP Tool Tests")
    print("=" * 60)

    # 1. Prepare search input
    params = FlightSearchInput(
        origin="BOM",
        destination="CDG",
        departure_date="2025-06-15",
        adults=2,
    )
    print(f"\n[1] Input: {params.origin} -> {params.destination} on {params.departure_date}")

    # 2. Call the tool (this will use mock data from AmadeusClient)
    try:
        results = await search_flights_tool(params)
        
        print(f"\n[2] Output: Successfully retrieved {len(results)} flight options")
        assert len(results) > 0, "Should have returned at least one flight option"
        
        # 3. Validate first flight option (mapping from mock data)
        first = results[0]
        print(f"\n[3] Validating first flight mapping (from mock data):")
        print(f"    Airline: {first.airline}")
        print(f"    Flight Number: {first.flight_number}")
        print(f"    Price: {first.price} {first.currency}")
        print(f"    Stops: {first.stops}")
        print(f"    Cabin: {first.cabin_class}")
        print(f"    Departure: {first.departure_time}")
        print(f"    Arrival: {first.arrival_time}")

        # Assertions based on MOCK_FLIGHT_RESPONSE in amadeus_client.py
        assert first.airline == "AIR FRANCE"
        assert first.flight_number == "AF 218"
        assert first.price == 856.0
        assert first.stops == 0
        assert first.cabin_class == "ECONOMY"
        assert first.origin == "BOM"
        assert first.destination == "CDG"
        
        # 4. Validate second flight option (if present in mock)
        if len(results) > 1:
            second = results[1]
            print(f"\n[4] Validating second flight mapping (from mock data):")
            print(f"    Airline: {second.airline}")
            print(f"    Price: {second.price}")
            assert second.airline == "LUFTHANSA"
            assert second.price == 692.0
            assert second.stops == 1  # Verify stop counting logic

        print("\n" + "=" * 60)
        print("✓ All M5 tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_search_flights_mock_parsing())
