"""
Greeting Agent node implementation.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from backend.agents.base_agent import BaseAgent, wrap_agent_error
from backend.agents.greeting_agent.prompts import (
    GREETING_SYSTEM_PROMPT,
    build_clarification_question,
)
from backend.schemas.travel_intent import TravelIntent
from backend.utils.logger import get_logger

logger = get_logger("agents.greeting")


class GreetingAgent(BaseAgent):
    """Extract TravelIntent from conversation and handle ambiguity."""

    def __init__(self, *, llm: Optional[Any] = None):
        super().__init__("greeting_agent", llm=llm)

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        user_text = _extract_latest_user_text(state)
        if not user_text:
            raise ValueError("No user message found in state for greeting agent.")

        try:
            messages = self.build_messages(
                GREETING_SYSTEM_PROMPT,
                user_input=user_text,
                additional_context=(
                    "You are in the greeting phase. Extract structured travel intent only."
                ),
            )
            intent = self.invoke_structured(messages, TravelIntent)

            if intent.is_complete():
                logger.info("GreetingAgent extracted complete intent.")
                return {
                    "travel_intent": intent,
                    "intent_confirmed": True,
                    "current_phase": "planning",
                }

            clarification = build_clarification_question(intent)
            logger.info("GreetingAgent extracted incomplete intent; requesting clarification.")
            return {
                "intent_confirmed": False,
                "current_phase": "greeting",
                "messages": [clarification],
            }

        except Exception as error:
            wrapped = wrap_agent_error(
                "greeting_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "greeting")},
            )
            return {
                "intent_confirmed": False,
                "current_phase": "greeting",
                "errors": [wrapped.message],
                "messages": [
                    "I could not fully understand your trip details. "
                    "Could you restate your destination, dates, and budget?"
                ],
            }


async def greeting_node(state: Mapping[str, Any], *, llm: Optional[Any] = None) -> dict[str, Any]:
    """LangGraph-compatible greeting node entrypoint."""
    agent = GreetingAgent(llm=llm)
    return await agent.run(state)


def _extract_latest_user_text(state: Mapping[str, Any]) -> str:
    """
    Extract the latest user-provided textual input from state.
    """
    messages = state.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            text = _message_to_text(item)
            if text:
                return text

    for key in ("user_input", "message", "input"):
        candidate = state.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    return ""


def _message_to_text(message: Any) -> str:
    if isinstance(message, str):
        return message.strip()

    if isinstance(message, dict):
        for key in ("content", "text", "message"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    return ""


__all__ = [
    "GreetingAgent",
    "greeting_node",
]
