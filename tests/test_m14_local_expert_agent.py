"""
Tests for Module M14: Local Expert Agent.

Validates:
- one broad query construction from TravelIntent
- local insights returned via MCP client wrapper
- clarification path for missing destination
- MCP failure fallback behavior
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.agents.local_expert_agent.agent import local_expert_node
from backend.schemas.itinerary import InsightCategory, LocalInsight
from backend.services.mcp_client import MCPClientError


class _FakeMCPClientSuccess:
    def __init__(self):
        self.called_with = None
        self.call_count = 0

    async def web_search_places(self, params):
        self.called_with = params
        self.call_count += 1
        return [
            LocalInsight(
                name="Le Marais Walk",
                category=InsightCategory.CULTURAL,
                description="A cultural neighborhood walk with food and art stops.",
                location="Paris",
                estimated_cost=20.0,
                duration_hours=2.5,
                source_url="https://example.com/paris-marais",
                rating=4.6,
            )
        ]

    async def close(self):
        return None


class _FakeMCPClientFailure:
    async def web_search_places(self, _params):
        raise MCPClientError("synthetic MCP failure")

    async def close(self):
        return None


async def test_m14_local_expert_agent():
    print("=" * 60)
    print("M14 Local Expert Agent Tests")
    print("=" * 60)

    # ── 1. Happy path + one broad query ─────────────────────────────
    print("\n[1] Testing broad-query mapping and MCP call...")
    success_client = _FakeMCPClientSuccess()
    state = {
        "travel_intent": {
            "destination": "Paris, France",
            "preferences": "food, museums, hidden gems",
            "special_requirements": "vegetarian-friendly options",
        },
        "current_phase": "planning",
    }
    result = await local_expert_node(state, mcp_client=success_client)
    assert isinstance(result.get("local_insights"), list)
    assert len(result["local_insights"]) == 1
    assert success_client.call_count == 1

    query = success_client.called_with.query.lower()
    assert "paris" in query
    assert "hidden gems" in query
    assert "food" in query
    print("  OK: one broad query built from destination + preferences")

    # ── 2. Clarification path for missing destination ───────────────
    print("\n[2] Testing missing-destination clarification...")
    incomplete_state = {
        "travel_intent": {
            "preferences": "nightlife",
        },
        "current_phase": "planning",
    }
    incomplete_result = await local_expert_node(incomplete_state, mcp_client=success_client)
    assert incomplete_result["current_phase"] == "planning"
    assert incomplete_result["local_insights"] == []
    assert isinstance(incomplete_result.get("messages"), list)
    assert "destination" in incomplete_result["messages"][0].lower()
    print("  OK: missing destination triggers clarification response")

    # ── 3. MCP failure fallback behavior ─────────────────────────────
    print("\n[3] Testing MCP failure fallback...")
    failing_state = {
        "travel_intent": {
            "destination": "Paris, France",
            "preferences": "culture",
        },
        "current_phase": "planning",
    }
    failing_result = await local_expert_node(
        failing_state, mcp_client=_FakeMCPClientFailure()
    )
    assert failing_result["local_insights"] == []
    assert isinstance(failing_result.get("errors"), list)
    assert len(failing_result["errors"]) == 1
    assert "local_expert_agent failed during run" in failing_result["errors"][0]
    print("  OK: MCP errors are wrapped with safe fallback response")

    # ── 4. Ensure no direct HTTP usage in local expert node ─────────
    print("\n[4] Testing no direct HTTP usage in local expert agent...")
    module = __import__("backend.agents.local_expert_agent.agent", fromlist=["*"])
    source = inspect.getsource(module)
    assert "httpx" not in source.lower()
    assert "MCPClient" in source
    print("  OK: local expert agent depends on MCPClient abstraction only")

    print("\n" + "=" * 60)
    print("✓ All M14 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m14_local_expert_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

