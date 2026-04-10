"""
Tests for Module M7: MCP Tool — web_search_places.
"""

import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.abspath("."))

from backend.mcp_servers.tools import web_search_places as tool
from backend.schemas.itinerary import InsightCategory, LocalInsight, WebSearchInput


@pytest.mark.asyncio
async def test_web_search_places_tavily_mapping_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTavilyClient:
        def __init__(self, api_key: str):
            self.api_key = api_key

        def search(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Louvre Museum in Paris",
                        "content": "A world-class museum with rich art history.",
                        "url": "https://example.com/louvre",
                    },
                    {
                        "title": "Le Marais Hidden Gem Walk",
                        "content": "A hidden gem route with cafe stops.",
                        "url": "https://example.com/marais",
                    },
                    {
                        "title": "Louvre Museum in Paris",
                        "content": "Duplicate listing should be deduped.",
                        "url": "https://example.com/louvre",
                    },
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(tool, "TavilyClient", FakeTavilyClient)

    params = WebSearchInput(
        query="hidden gems in Paris for food lovers",
        search_depth="advanced",
        max_results=2,
    )
    results = await tool.web_search_places_tool(params)

    assert len(results) == 2
    assert all(isinstance(item, LocalInsight) for item in results)
    assert results[0].category in {
        InsightCategory.ATTRACTION,
        InsightCategory.CULTURAL,
    }
    assert results[1].category == InsightCategory.HIDDEN_GEM


@pytest.mark.asyncio
async def test_web_search_places_passes_include_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeTavilyClient:
        def __init__(self, api_key: str):
            self.api_key = api_key

        def search(self, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {
                "results": [
                    {
                        "title": "Tripadvisor Paris Food",
                        "content": "Great local dining suggestions.",
                        "url": "https://tripadvisor.com/paris-food",
                    }
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(tool, "TavilyClient", FakeTavilyClient)

    params = WebSearchInput(
        query="best local dining in Paris",
        include_domains=["tripadvisor.com", "lonelyplanet.com"],
        max_results=5,
    )
    results = await tool.web_search_places_tool(params)

    assert len(results) == 1
    assert captured["include_domains"] == ["tripadvisor.com", "lonelyplanet.com"]


@pytest.mark.asyncio
async def test_web_search_places_skips_malformed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_tavily(_input_params: WebSearchInput) -> list[dict[str, Any]]:
        return [
            {"title": "Valid Attraction", "content": "A must-see landmark.", "url": "https://a.com"},
            "not-a-dict",  # malformed
        ]

    monkeypatch.setattr(tool, "_search_with_tavily", fake_tavily)

    params = WebSearchInput(query="things to do in Paris", max_results=5)
    results = await tool.web_search_places_tool(params)

    assert len(results) == 1
    assert results[0].name == "Valid Attraction"


@pytest.mark.asyncio
async def test_web_search_places_uses_fallback_on_tavily_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_tavily(_input_params: WebSearchInput) -> list[dict[str, Any]]:
        raise RuntimeError("Tavily unavailable")

    def fallback_results(_input_params: WebSearchInput) -> list[dict[str, Any]]:
        return [
            {
                "title": "Secret Courtyard in Paris",
                "content": "A hidden gem that takes 2 hours and costs $15.",
                "url": "https://example.com/secret-courtyard",
            }
        ]

    monkeypatch.setattr(tool, "_search_with_tavily", failing_tavily)
    monkeypatch.setattr(tool, "_search_with_fallback", fallback_results)

    params = WebSearchInput(query="hidden gems in Paris", max_results=3)
    results = await tool.web_search_places_tool(params)

    assert len(results) == 1
    assert results[0].category == InsightCategory.HIDDEN_GEM
    assert results[0].estimated_cost == 15.0
    assert results[0].duration_hours == 2.0


@pytest.mark.asyncio
async def test_web_search_places_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "_search_with_tavily", lambda _params: [])

    params = WebSearchInput(query="quiet places in Paris", max_results=5)
    results = await tool.web_search_places_tool(params)

    assert results == []
