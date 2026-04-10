"""
Tests for Module M6: MCP Tool — search_hotels.

Validates that the search_hotels_tool correctly calls the AmadeusClient
(two-step process) and parses the raw responses into HotelOption Pydantic models.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from backend.mcp_servers.tools.search_hotels import search_hotels_tool
from backend.schemas.accommodation import HotelSearchInput, HotelOption, PriceRange


async def test_search_hotels_mock_parsing():
    print("=" * 60)
    print("M6 search_hotels MCP Tool Tests")
    print("=" * 60)

    # 1. Prepare search input
    params = HotelSearchInput(
        city_code="PAR",
        check_in="2025-06-15",
        check_out="2025-06-22",
        adults=2,
        max_results=5,
    )
    print(f"\n[1] Input: city={params.city_code} from {params.check_in} to {params.check_out}")

    # 2. Call the tool (this will use mock data from AmadeusClient)
    try:
        results = await search_hotels_tool(params)
        
        print(f"\n[2] Output: Successfully retrieved {len(results)} hotel options")
        assert len(results) > 0, "Should have returned at least one hotel option"
        
        # 3. Validate first hotel option (mapping from mock data)
        first = results[0]
        print(f"\n[3] Validating first hotel mapping (from mock data):")
        print(f"    Name: {first.name}")
        print(f"    Rating: {first.rating}")
        print(f"    Price per night: {first.price_per_night} {first.currency}")
        print(f"    Total Price: {first.total_price}")
        print(f"    Address: {first.address}")
        print(f"    Amenities: {first.amenities[:3]}...")

        # Assertions based on MOCK_HOTEL_OFFERS_RESPONSE in amadeus_client.py
        assert first.name == "Hotel Le Marais"
        assert first.rating == 4.0
        assert first.price_per_night == 140.0
        assert first.total_price == 1120.0
        assert "Paris" in first.address
        assert first.currency == "USD"
        
        # 4. Test price range filtering (mid range should include Hotel Le Marais at 140)
        print("\n[4] Testing mid-range filtering...")
        params.price_range = PriceRange.MID
        mid_results = await search_hotels_tool(params)
        assert any(h.name == "Hotel Le Marais" for h in mid_results)
        print("    OK: Mid-range filtering works")

        # 5. Test price range filtering (budget should include Budget Inn at 80)
        print("\n[5] Testing budget filtering...")
        params.price_range = PriceRange.BUDGET
        budget_results = await search_hotels_tool(params)
        assert any("Budget" in h.name for h in budget_results)
        assert not any(h.name == "Hotel Le Marais" for h in budget_results)
        print("    OK: Budget filtering works")

        print("\n" + "=" * 60)
        print("✓ All M6 tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_search_hotels_mock_parsing())
