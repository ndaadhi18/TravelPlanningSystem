"""
Tests for Module M7: MCP Tool - web_search_places.

Validates that the web_search_places_tool correctly maps provider results
into LocalInsight Pydantic models, handles malformed records, and falls
back when the primary provider fails.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.mcp_servers.tools import web_search_places as tool_module
from backend.schemas.itinerary import InsightCategory, LocalInsight, WebSearchInput


async def test_web_search_places_mock_parsing():
    print("=" * 60)
    print("M7 web_search_places MCP Tool Tests")
    print("=" * 60)

    original_tavily = tool_module._search_with_tavily
    original_fallback = tool_module._search_with_fallback

    try:
        # 1. Prepare search input
        params = WebSearchInput(
            query="hidden gems in Paris for food lovers",
            search_depth="advanced",
            max_results=2,
        )
        print(
            f"\n[1] Input: query='{params.query}', "
            f"depth={params.search_depth}, max_results={params.max_results}"
        )

        # 2. Primary provider mapping
        def fake_tavily(_input_params: WebSearchInput):
            return [
                {
                    "title": "Louvre Museum in Paris",
                    "content": "A world-class museum and landmark for art lovers.",
                    "url": "https://example.com/louvre",
                },
                {
                    "title": "Le Marais Hidden Gem Walk",
                    "content": "A hidden gem route with cafe stops.",
                    "url": "https://example.com/marais",
                },
                {
                    "title": "Louvre Museum in Paris",
                    "content": "Duplicate should be deduped.",
                    "url": "https://example.com/louvre",
                },
            ]

        tool_module._search_with_tavily = fake_tavily
        results = await tool_module.web_search_places_tool(params)

        print(f"\n[2] Output: Successfully retrieved {len(results)} local insights")
        assert len(results) == 2, "Should return 2 insights (deduped + capped)"
        assert all(isinstance(item, LocalInsight) for item in results)

        first = results[0]
        second = results[1]
        print("\n[3] Validating mapped insights:")
        print(f"    First: {first.name} | category={first.category} | url={first.source_url}")
        print(f"    Second: {second.name} | category={second.category} | url={second.source_url}")

        assert first.category in (InsightCategory.ATTRACTION, InsightCategory.CULTURAL)
        assert second.category == InsightCategory.HIDDEN_GEM

        # 3. Malformed record should be skipped
        print("\n[4] Testing malformed record skip...")

        def fake_tavily_with_bad(_input_params: WebSearchInput):
            return [
                {
                    "title": "Eiffel Tower at Night",
                    "content": "A classic landmark experience.",
                    "url": "https://example.com/eiffel",
                },
                "not-a-dict",
            ]

        tool_module._search_with_tavily = fake_tavily_with_bad
        params.max_results = 5
        malformed_results = await tool_module.web_search_places_tool(params)
        assert len(malformed_results) == 1
        assert malformed_results[0].name == "Eiffel Tower at Night"
        print("    OK: Malformed result skipped without failing the request")

        # 4. Fallback path when primary provider fails
        print("\n[5] Testing fallback flow...")

        def failing_tavily(_input_params: WebSearchInput):
            raise RuntimeError("Tavily unavailable")

        def fake_fallback(_input_params: WebSearchInput):
            return [
                {
                    "title": "Secret Courtyard in Paris",
                    "content": "A hidden gem that takes 2 hours and costs $15.",
                    "url": "https://example.com/secret-courtyard",
                }
            ]

        tool_module._search_with_tavily = failing_tavily
        tool_module._search_with_fallback = fake_fallback

        fallback_results = await tool_module.web_search_places_tool(params)
        assert len(fallback_results) == 1
        assert fallback_results[0].category == InsightCategory.HIDDEN_GEM
        assert fallback_results[0].estimated_cost == 15.0
        assert fallback_results[0].duration_hours == 2.0
        print("    OK: Fallback branch works and maps to LocalInsight")

        # 5. Empty response behavior
        print("\n[6] Testing empty response...")
        tool_module._search_with_tavily = lambda _input_params: []
        tool_module._search_with_fallback = original_fallback
        empty_results = await tool_module.web_search_places_tool(params)
        assert empty_results == []
        print("    OK: Empty provider response returns []")

        print("\n" + "=" * 60)
        print("✓ All M7 tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        tool_module._search_with_tavily = original_tavily
        tool_module._search_with_fallback = original_fallback


if __name__ == "__main__":
    asyncio.run(test_web_search_places_mock_parsing())
