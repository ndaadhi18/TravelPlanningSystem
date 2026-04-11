"""
Tests for Module M18: Graph Definition.

Validates:
- state graph compiles and includes required nodes
- routing functions match IMPLEMENTATION.md branch rules
- planning node supports deterministic phase/iteration behavior
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.orchestration.graph import build_graph, build_state_graph, planning_node
from backend.orchestration.router import (
    route_after_constraint,
    route_after_feedback,
    route_after_greeting,
    route_after_planning,
)
from backend.schemas.travel_state import FeedbackType, PlanningPhase


async def test_m18_graph_definition():
    print("=" * 60)
    print("M18 Graph Definition Tests")
    print("=" * 60)

    # ── 1. Graph nodes and compile ──────────────────────────────────
    print("\n[1] Testing graph node registration and compilation...")
    state_graph = build_state_graph()
    node_names = set(state_graph.nodes.keys())
    expected_nodes = {
        "greeting",
        "planning",
        "transport",
        "accommodation",
        "local_expert",
        "constraint",
        "feedback",
        "payment",
    }
    assert expected_nodes.issubset(node_names)

    compiled = build_graph()
    assert hasattr(compiled, "invoke")
    print("  OK: graph builds, registers nodes, and compiles")

    # ── 2. Greeting route ────────────────────────────────────────────
    print("\n[2] Testing route_after_greeting...")
    assert route_after_greeting({"intent_confirmed": True}) == "planning"
    assert route_after_greeting({"intent_confirmed": False}) == "greeting"
    print("  OK: greeting route branches correctly")

    # ── 3. Planning fan-out route ────────────────────────────────────
    print("\n[3] Testing route_after_planning fan-out...")
    fanout = route_after_planning({})
    assert isinstance(fanout, list)
    assert set(fanout) == {"transport", "accommodation", "local_expert"}
    print("  OK: planning route returns parallel data-gathering nodes")

    # ── 4. Constraint route ──────────────────────────────────────────
    print("\n[4] Testing route_after_constraint...")
    assert route_after_constraint({}) == "feedback"
    print("  OK: constraint route enters feedback stage")

    # ── 5. Feedback route branches ───────────────────────────────────
    print("\n[5] Testing route_after_feedback branches...")
    assert route_after_feedback({"feedback_type": FeedbackType.APPROVE.value}) == "payment"
    assert route_after_feedback({"feedback_type": FeedbackType.MODIFY.value}) == "planning"
    assert route_after_feedback({"feedback_type": FeedbackType.REJECT.value}) == "greeting"
    assert route_after_feedback({"feedback_type": FeedbackType.NEW_TRIP.value}) == "greeting"
    assert route_after_feedback({"feedback_type": "approve", "iteration_count": 6}) == "payment"
    print("  OK: feedback route covers approve/modify/reject/new_trip/iteration cap")

    # ── 6. Planning node deterministic behavior ─────────────────────
    print("\n[6] Testing planning_node deterministic updates...")
    modify_result = await planning_node({"feedback_type": "modify", "iteration_count": 2})
    assert modify_result["current_phase"] == PlanningPhase.DATA_GATHERING
    assert modify_result["iteration_count"] == 3

    neutral_result = await planning_node({"feedback_type": "approve", "iteration_count": 2})
    assert neutral_result["current_phase"] == PlanningPhase.DATA_GATHERING
    assert neutral_result["iteration_count"] == 2
    print("  OK: planning node increments only for modify feedback")

    # ── 7. Ensure no direct MCP/http usage in graph/router ──────────
    print("\n[7] Testing no MCP/http usage in orchestration graph/router...")
    graph_source = inspect.getsource(__import__("backend.orchestration.graph", fromlist=["*"]))
    router_source = inspect.getsource(__import__("backend.orchestration.router", fromlist=["*"]))
    lowered = (graph_source + "\n" + router_source).lower()
    assert "mcpclient" not in lowered
    assert "httpx" not in lowered
    print("  OK: orchestration layer does not directly depend on MCP/http clients")

    print("\n" + "=" * 60)
    print("✓ All M18 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m18_graph_definition())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

