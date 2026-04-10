"""
Tests for Module M11: Greeting Agent.

Validates:
- TravelIntent extraction on complete input
- ambiguity handling with clarification message
- no MCP client usage in greeting node
- graceful error path behavior
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.agents.greeting_agent.agent import GreetingAgent, greeting_node
from backend.schemas.travel_intent import TravelIntent


class _CompleteIntentLLM:
    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, _messages):
        return TravelIntent(
            destination="Paris, France",
            budget=2500.0,
            start_date="2025-06-15",
            duration_days=5,
            num_travelers=2,
        )


class _IncompleteIntentLLM:
    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, _messages):
        return TravelIntent(destination="Paris, France")


class _FailingLLM:
    def with_structured_output(self, _model_cls):
        return self

    def invoke(self, _messages):
        raise RuntimeError("synthetic LLM failure")


async def test_m11_greeting_agent():
    print("=" * 60)
    print("M11 Greeting Agent Tests")
    print("=" * 60)

    # ── 1. Complete intent extraction ─────────────────────────────
    print("\n[1] Testing complete intent extraction...")
    complete_state = {
        "messages": [
            "Plan a 5 day trip to Paris for 2 people with a budget of 2500 USD."
        ],
        "current_phase": "greeting",
    }
    complete_result = await greeting_node(complete_state, llm=_CompleteIntentLLM())
    assert complete_result["intent_confirmed"] is True
    assert complete_result["current_phase"] == "planning"
    assert isinstance(complete_result["travel_intent"], TravelIntent)
    print("  OK: complete intent sets travel_intent and intent_confirmed=True")

    # ── 2. Incomplete intent clarification ────────────────────────
    print("\n[2] Testing incomplete intent clarification...")
    incomplete_state = {
        "messages": ["I want to visit Paris sometime soon."],
        "current_phase": "greeting",
    }
    incomplete_result = await greeting_node(incomplete_state, llm=_IncompleteIntentLLM())
    assert incomplete_result["intent_confirmed"] is False
    assert incomplete_result["current_phase"] == "greeting"
    assert isinstance(incomplete_result.get("messages"), list)
    assert len(incomplete_result["messages"]) > 0
    clarification_text = incomplete_result["messages"][0].lower()
    assert ("budget" in clarification_text) or ("dates" in clarification_text)
    print("  OK: ambiguity handled via clarification message")

    # ── 3. No MCP client usage in greeting module ─────────────────
    print("\n[3] Testing no-MCP usage in greeting agent...")
    source = inspect.getsource(__import__("backend.agents.greeting_agent.agent", fromlist=["*"]))
    assert "mcp_client" not in source.lower()
    print("  OK: greeting agent has no MCP client dependency")

    # ── 4. Error path handling ─────────────────────────────────────
    print("\n[4] Testing greeting error path...")
    failing_state = {
        "messages": ["Book a luxury trip to Japan."],
        "current_phase": "greeting",
    }
    failing_result = await greeting_node(failing_state, llm=_FailingLLM())
    assert failing_result["intent_confirmed"] is False
    assert failing_result["current_phase"] == "greeting"
    assert isinstance(failing_result.get("errors"), list)
    assert len(failing_result["errors"]) == 1
    assert "greeting_agent failed during run" in failing_result["errors"][0]
    print("  OK: errors are wrapped and returned in a stable fallback response")

    print("\n" + "=" * 60)
    print("✓ All M11 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m11_greeting_agent())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
