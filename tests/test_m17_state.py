"""
Tests for Module M17: LangGraph state definitions.

Validates:
- TravelState TypedDict fields align with shared-state contract
- reducer annotations are configured for messages/errors
- initial-state helper returns safe defaults
"""

import os
import sys
from typing import Annotated, get_args, get_origin, get_type_hints

sys.path.insert(0, os.path.abspath("."))

import operator

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from backend.orchestration.state import TravelState, create_initial_state
from backend.schemas.travel_state import PlanningPhase


def test_m17_state():
    print("=" * 60)
    print("M17 LangGraph State Tests")
    print("=" * 60)

    annotations = get_type_hints(TravelState, include_extras=True)

    # ── 1. Required state keys ─────────────────────────────────────
    print("\n[1] Testing TravelState keys...")
    expected_keys = {
        "messages",
        "travel_intent",
        "intent_confirmed",
        "flight_options",
        "hotel_options",
        "local_insights",
        "itinerary",
        "budget_summary",
        "feedback",
        "feedback_type",
        "iteration_count",
        "booking_confirmation",
        "current_phase",
        "errors",
    }
    assert expected_keys.issubset(set(annotations.keys()))
    print("  OK: all expected state keys exist")

    # ── 2. Reducer annotations ─────────────────────────────────────
    print("\n[2] Testing reducer annotations...")
    messages_ann = annotations["messages"]
    errors_ann = annotations["errors"]

    assert get_origin(messages_ann) is Annotated
    messages_args = get_args(messages_ann)
    assert get_origin(messages_args[0]) is list
    assert get_args(messages_args[0])[0] is AnyMessage
    assert messages_args[1] is add_messages

    assert get_origin(errors_ann) is Annotated
    errors_args = get_args(errors_ann)
    assert get_origin(errors_args[0]) is list
    assert get_args(errors_args[0])[0] is str
    assert errors_args[1] is operator.add
    print("  OK: messages/errors reducers are correctly configured")

    # ── 3. Initial state defaults ──────────────────────────────────
    print("\n[3] Testing initial state defaults...")
    initial = create_initial_state()
    assert initial["messages"] == []
    assert initial["travel_intent"] is None
    assert initial["intent_confirmed"] is False
    assert initial["flight_options"] == []
    assert initial["hotel_options"] == []
    assert initial["local_insights"] == []
    assert initial["itinerary"] is None
    assert initial["budget_summary"] is None
    assert initial["feedback"] is None
    assert initial["feedback_type"] is None
    assert initial["iteration_count"] == 0
    assert initial["booking_confirmation"] is None
    assert initial["current_phase"] == PlanningPhase.GREETING
    assert initial["errors"] == []
    print("  OK: create_initial_state returns stable defaults")

    # ── 4. Compatibility with agent update keys ────────────────────
    print("\n[4] Testing compatibility with agent update keys...")
    agent_update_keys = {
        "travel_intent",
        "intent_confirmed",
        "flight_options",
        "hotel_options",
        "local_insights",
        "itinerary",
        "budget_summary",
        "booking_confirmation",
        "current_phase",
        "errors",
        "messages",
    }
    assert agent_update_keys.issubset(set(annotations.keys()))
    print("  OK: state keys are compatible with M11-M16 agent updates")

    print("\n" + "=" * 60)
    print("✓ All M17 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_m17_state()
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

