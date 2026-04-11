"""
Tests for Module M19: End-to-End Flow (greeting -> itinerary generation).

Guarded mode:
- If required runtime dependencies are not available (env keys, MCP server),
  the script prints a clear SKIP message and exits successfully.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Mapping, Optional

sys.path.insert(0, os.path.abspath("."))

from langchain_core.messages import HumanMessage

from backend.core.settings import get_settings
from backend.orchestration.graph import build_graph, build_state_graph
from backend.orchestration.state import create_initial_state
from backend.services.mcp_client import MCPClient
from backend.utils.logger import get_logger

logger = get_logger("tests.m19_end_to_end")


async def test_m19_end_to_end():
    print("=" * 60)
    print("M19 End-to-End Integration Test")
    print("=" * 60)

    skip_reason = await _guard_runtime_requirements()
    if skip_reason:
        print(f"\nSKIP: {skip_reason}")
        print("=" * 60)
        print("✓ M19 guarded skip (non-failure)")
        print("=" * 60)
        return

    # Build graph with checkpointer support for human-in-the-loop interrupt.
    graph = _build_compiled_graph()

    prompt = (
        "Plan a 5 day trip from Mumbai to Paris for 2 people from 2026-07-10 to 2026-07-15 "
        "with a budget of 3500 USD. We like art museums, local food, and hidden gems."
    )
    initial_state = create_initial_state(messages=[HumanMessage(content=prompt)])
    config = {"configurable": {"thread_id": "m19-e2e-thread"}, "recursion_limit": 40}

    print("\n[1] Running compiled graph from greeting to feedback boundary...")
    result = await _invoke_graph(graph, initial_state, config=config)
    assert isinstance(result, dict), "Graph result must be a dict-like state payload."
    print("  OK: graph invocation returned state payload")

    print("\n[2] Verifying greeting and itinerary generation artifacts...")
    travel_intent = result.get("travel_intent")
    itinerary = result.get("itinerary")
    budget_summary = result.get("budget_summary")
    interrupt_payload = _extract_interrupt_payload(result.get("__interrupt__"))

    if travel_intent is None and interrupt_payload:
        travel_intent = interrupt_payload.get("travel_intent")
    if itinerary is None and interrupt_payload:
        itinerary = interrupt_payload.get("itinerary")
    if budget_summary is None and interrupt_payload:
        budget_summary = interrupt_payload.get("budget_summary")

    assert travel_intent is not None, "Expected travel_intent from greeting stage."
    assert itinerary is not None, "Expected itinerary output from constraint stage."
    assert budget_summary is not None, "Expected budget_summary output from constraint stage."
    print("  OK: travel_intent, itinerary, and budget_summary are present")

    print("\n[3] Verifying flow stops at feedback boundary...")
    phase = str(result.get("current_phase", "")).lower()
    if phase:
        assert "feedback" in phase, f"Expected feedback phase boundary, got phase={phase!r}"
    else:
        # Some LangGraph interrupt outputs omit current_phase in top-level response.
        assert result.get("__interrupt__") is not None, (
            "Expected feedback boundary via current_phase or interrupt payload."
        )
    print("  OK: flow reached feedback boundary (human-in-the-loop)")

    print("\n[4] Verifying gathered-data shape...")
    for key in ("flight_options", "hotel_options", "local_insights"):
        value = result.get(key, [])
        assert isinstance(value, list), f"{key} should be a list in graph state."
    print("  OK: gathered data keys are list-shaped")

    print("\n" + "=" * 60)
    print("✓ M19 integration flow passed!")
    print("=" * 60)


async def _guard_runtime_requirements() -> Optional[str]:
    """
    Return skip reason when guarded real-service requirements are not met.
    """
    try:
        settings = get_settings()
    except Exception as e:
        return (
            "Settings are not configured for real run "
            f"(missing/invalid env keys): {e}"
        )

    if not settings.groq_api_key.strip():
        return "GROQ_API_KEY is empty; real LLM run is unavailable."

    selected_transport = os.getenv("MCP_TRANSPORT", "streamable-http").strip().lower()
    if selected_transport in {"stdio", ""}:
        return (
            "MCP_TRANSPORT=stdio is not reachable by MCPClient (HTTP). "
            "Start MCP in streamable-http mode."
        )

    mcp_client = MCPClient()
    try:
        healthy = await mcp_client.health_check()
    except Exception as e:
        return f"MCP health check failed: {e}"
    finally:
        await mcp_client.close()

    if not healthy:
        return (
            f"MCP server is unreachable at {settings.mcp_server_url}. "
            "Start backend.mcp_servers.server in streamable-http mode."
        )

    return None


def _build_compiled_graph():
    """
    Prefer graph compilation with an in-memory checkpointer for interrupt support.
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver  # type: ignore
    except Exception:
        try:
            from langgraph.checkpoint.memory import InMemorySaver as MemorySaver  # type: ignore
        except Exception:
            MemorySaver = None  # type: ignore

    if MemorySaver is not None:
        try:
            return build_state_graph().compile(checkpointer=MemorySaver())
        except Exception as e:
            logger.warning(
                f"Falling back to default compile() because checkpointer compile failed: {e}"
            )

    return build_graph()


async def _invoke_graph(graph: Any, state: Mapping[str, Any], *, config: dict[str, Any]) -> dict[str, Any]:
    if hasattr(graph, "ainvoke"):
        return await graph.ainvoke(state, config=config)
    return graph.invoke(state, config=config)


def _extract_interrupt_payload(raw_interrupt: Any) -> dict[str, Any]:
    if raw_interrupt is None:
        return {}

    first = None
    if isinstance(raw_interrupt, list) and raw_interrupt:
        first = raw_interrupt[0]
    elif isinstance(raw_interrupt, tuple) and raw_interrupt:
        first = raw_interrupt[0]
    else:
        first = raw_interrupt

    if isinstance(first, Mapping):
        if isinstance(first.get("value"), Mapping):
            return dict(first["value"])
        return dict(first)

    value_attr = getattr(first, "value", None)
    if isinstance(value_attr, Mapping):
        return dict(value_attr)

    return {}


if __name__ == "__main__":
    try:
        asyncio.run(test_m19_end_to_end())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

