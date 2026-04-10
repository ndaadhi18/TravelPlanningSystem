"""
Transport Agent node implementation.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from pydantic import ValidationError

from backend.agents.base_agent import AgentExecutionError, BaseAgent, wrap_agent_error
from backend.agents.transport_agent.prompts import (
    TRANSPORT_SYSTEM_PROMPT,
    build_transport_clarification,
)
from backend.schemas.transport import FlightSearchInput
from backend.schemas.travel_intent import TravelIntent
from backend.services.mcp_client import MCPClient
from backend.utils.logger import get_logger

logger = get_logger("agents.transport")

_CITY_TO_IATA = {
    "mumbai": "BOM",
    "bombay": "BOM",
    "delhi": "DEL",
    "new delhi": "DEL",
    "paris": "CDG",
    "london": "LHR",
    "new york": "JFK",
    "san francisco": "SFO",
    "tokyo": "HND",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA",
    "singapore": "SIN",
    "dubai": "DXB",
}


class TransportAgent(BaseAgent):
    """Construct flight search params from intent and fetch flight options."""

    def __init__(
        self,
        *,
        llm: Optional[Any] = None,
        mcp_client: Optional[MCPClient] = None,
    ):
        super().__init__("transport_agent", llm=llm)
        self._mcp_client = mcp_client

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_intent(state.get("travel_intent"))
        if intent is None:
            clarification = build_transport_clarification(
                ["departure city", "destination", "departure date"]
            )
            return {
                "flight_options": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        missing_fields = _missing_transport_fields(intent)
        if missing_fields:
            clarification = build_transport_clarification(missing_fields)
            return {
                "flight_options": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        mcp_client = self._mcp_client or MCPClient()
        owns_mcp_client = self._mcp_client is None

        try:
            search_input = self._build_search_input(intent, state)
            logger.info(
                f"TransportAgent searching flights {search_input.origin} -> "
                f"{search_input.destination} on {search_input.departure_date}"
            )
            flights = await mcp_client.search_flights(search_input)
            return {
                "flight_options": flights,
            }

        except Exception as error:
            wrapped = wrap_agent_error(
                "transport_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "planning")},
            )
            return {
                "flight_options": [],
                "errors": [wrapped.message],
                "messages": [
                    "I couldn't fetch flight options right now. "
                    "Please confirm your route and date, then I will try again."
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
    ) -> FlightSearchInput:
        if self._llm is not None:
            user_input = ""
            messages_from_state = state.get("messages")
            if isinstance(messages_from_state, list) and messages_from_state:
                last_message = messages_from_state[-1]
                user_input = str(last_message)

            messages = self.build_messages(
                TRANSPORT_SYSTEM_PROMPT,
                state={"travel_intent": intent.model_dump(mode="json")},
                user_input=user_input,
            )
            try:
                return self.invoke_structured(messages, FlightSearchInput)
            except AgentExecutionError:
                logger.warning(
                    "LLM transport-parameter mapping failed; using deterministic fallback."
                )

        return _build_flight_search_input(intent)


async def transport_node(
    state: Mapping[str, Any],
    *,
    llm: Optional[Any] = None,
    mcp_client: Optional[MCPClient] = None,
) -> dict[str, Any]:
    """LangGraph-compatible transport node entrypoint."""
    agent = TransportAgent(llm=llm, mcp_client=mcp_client)
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


def _missing_transport_fields(intent: TravelIntent) -> list[str]:
    missing: list[str] = []
    if not intent.source_location:
        missing.append("departure city")
    if not intent.destination:
        missing.append("destination")
    if not intent.start_date:
        missing.append("departure date")
    return missing


def _build_flight_search_input(intent: TravelIntent) -> FlightSearchInput:
    origin = _resolve_iata_code(intent.source_location or "")
    destination = _resolve_iata_code(intent.destination or "")

    return FlightSearchInput(
        origin=origin,
        destination=destination,
        departure_date=intent.start_date or "",
        return_date=_normalize_return_date(intent.start_date, intent.end_date),
        adults=max(1, int(intent.num_travelers)),
        max_results=5,
        currency=intent.currency or "USD",
    )


def _resolve_iata_code(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    lowered = cleaned.lower()
    for city, code in _CITY_TO_IATA.items():
        if city in lowered:
            return code

    letters = "".join(ch for ch in cleaned.upper() if ch.isalpha())
    if len(letters) >= 3:
        return letters[:3]
    return "UNK"


def _normalize_return_date(
    start_date: Optional[str],
    end_date: Optional[str],
) -> Optional[str]:
    if not start_date or not end_date:
        return None
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return None
    return end_date if end > start else None


__all__ = [
    "TransportAgent",
    "transport_node",
]
