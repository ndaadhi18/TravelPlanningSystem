"""
Local Expert Agent node implementation.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from pydantic import ValidationError

from backend.agents.base_agent import AgentExecutionError, BaseAgent, wrap_agent_error
from backend.agents.local_expert_agent.prompts import (
    LOCAL_EXPERT_SYSTEM_PROMPT,
    build_local_expert_clarification,
)
from backend.schemas.itinerary import SearchDepth, WebSearchInput
from backend.schemas.travel_intent import TravelIntent
from backend.services.mcp_client import MCPClient
from backend.utils.logger import get_logger

logger = get_logger("agents.local_expert")


class LocalExpertAgent(BaseAgent):
    """Discover local insights using one broad web query via MCP."""

    def __init__(
        self,
        *,
        llm: Optional[Any] = None,
        mcp_client: Optional[MCPClient] = None,
    ):
        super().__init__("local_expert_agent", llm=llm)
        self._mcp_client = mcp_client

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_intent(state.get("travel_intent"))
        if intent is None:
            clarification = build_local_expert_clarification(["destination"])
            return {
                "local_insights": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        missing_fields = _missing_local_expert_fields(intent)
        if missing_fields:
            clarification = build_local_expert_clarification(missing_fields)
            return {
                "local_insights": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        mcp_client = self._mcp_client or MCPClient()
        owns_mcp_client = self._mcp_client is None

        try:
            search_input = self._build_search_input(intent, state)
            logger.info(f"LocalExpertAgent searching local insights for '{search_input.query}'")
            insights = await mcp_client.web_search_places(search_input)
            return {
                "local_insights": insights,
            }
        except Exception as error:
            wrapped = wrap_agent_error(
                "local_expert_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "planning")},
            )
            return {
                "local_insights": [],
                "errors": [wrapped.message],
                "messages": [
                    "I couldn't fetch local insights right now. "
                    "Please confirm your destination and preferences, then I will try again."
                ],
                "current_phase": "planning",
            }
        finally:
            if owns_mcp_client:
                await mcp_client.close()

    def _build_search_input(
        self,
        intent: TravelIntent,
        state: Mapping[str, Any],
    ) -> WebSearchInput:
        if self._llm is not None:
            messages = self.build_messages(
                LOCAL_EXPERT_SYSTEM_PROMPT,
                state={"travel_intent": intent.model_dump(mode="json")},
                user_input=_extract_latest_user_text(state),
            )
            try:
                return self.invoke_structured(messages, WebSearchInput)
            except AgentExecutionError:
                logger.warning(
                    "LLM local-expert query mapping failed; using deterministic fallback."
                )

        return _build_web_search_input(intent)


async def local_expert_node(
    state: Mapping[str, Any],
    *,
    llm: Optional[Any] = None,
    mcp_client: Optional[MCPClient] = None,
) -> dict[str, Any]:
    """LangGraph-compatible local expert node entrypoint."""
    agent = LocalExpertAgent(llm=llm, mcp_client=mcp_client)
    return await agent.run(state)


def _normalize_intent(raw_intent: Any) -> Optional[TravelIntent]:
    if raw_intent is None:
        return None
    if isinstance(raw_intent, TravelIntent):
        return raw_intent
    if isinstance(raw_intent, Mapping):
        try:
            return TravelIntent.model_validate(raw_intent)
        except ValidationError:
            return None
    return None


def _missing_local_expert_fields(intent: TravelIntent) -> list[str]:
    missing: list[str] = []
    if not intent.destination:
        missing.append("destination")
    return missing


def _build_web_search_input(intent: TravelIntent) -> WebSearchInput:
    query = _compose_broad_query(intent)
    depth = SearchDepth.ADVANCED if intent.preferences else SearchDepth.BASIC
    return WebSearchInput(
        query=query,
        search_depth=depth,
        max_results=5,
        include_domains=None,
    )


def _compose_broad_query(intent: TravelIntent) -> str:
    destination = (intent.destination or "").strip()
    base = (
        "best attractions, hidden gems, local food spots, and cultural experiences in "
        f"{destination}"
    )
    if intent.preferences:
        base = f"{base} for {intent.preferences.strip()}"
    if intent.special_requirements:
        base = f"{base}. consider {intent.special_requirements.strip()}"
    # WebSearchInput caps query length at 500 chars.
    return base[:500]


def _extract_latest_user_text(state: Mapping[str, Any]) -> str:
    messages = state.get("messages")
    if isinstance(messages, list) and messages:
        candidate = messages[-1]
        if isinstance(candidate, str):
            return candidate.strip()
        if isinstance(candidate, dict):
            text = candidate.get("content")
            if isinstance(text, str):
                return text.strip()
        content = getattr(candidate, "content", None)
        if isinstance(content, str):
            return content.strip()
    return ""


__all__ = [
    "LocalExpertAgent",
    "local_expert_node",
]
