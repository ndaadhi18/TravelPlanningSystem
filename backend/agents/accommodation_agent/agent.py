"""
Accommodation Agent node implementation.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Optional

from pydantic import ValidationError

from backend.agents.base_agent import AgentExecutionError, BaseAgent, wrap_agent_error
from backend.agents.accommodation_agent.prompts import (
    ACCOMMODATION_SYSTEM_PROMPT,
    build_accommodation_clarification,
)
from backend.schemas.accommodation import HotelSearchInput, PriceRange
from backend.schemas.travel_intent import TravelIntent, TravelStyle
from backend.services.mcp_client import MCPClient
from backend.utils.logger import get_logger

logger = get_logger("agents.accommodation")

_CITY_TO_CODE = {
    "paris": "PAR",
    "london": "LON",
    "new york": "NYC",
    "mumbai": "BOM",
    "bombay": "BOM",
    "delhi": "DEL",
    "new delhi": "DEL",
    "tokyo": "TYO",
    "singapore": "SIN",
    "dubai": "DXB",
    "rome": "ROM",
    "barcelona": "BCN",
    "amsterdam": "AMS",
    "berlin": "BER",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA",
    "san francisco": "SFO",
}


class AccommodationAgent(BaseAgent):
    """Construct hotel search params from intent and fetch hotel options."""

    def __init__(
        self,
        *,
        llm: Optional[Any] = None,
        mcp_client: Optional[MCPClient] = None,
    ):
        super().__init__("accommodation_agent", llm=llm)
        self._mcp_client = mcp_client

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_intent(state.get("travel_intent"))
        if intent is None:
            clarification = build_accommodation_clarification(
                ["destination", "check-in date", "trip end date or duration"]
            )
            return {
                "hotel_options": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        missing_fields = _missing_accommodation_fields(intent)
        if missing_fields:
            clarification = build_accommodation_clarification(missing_fields)
            return {
                "hotel_options": [],
                "messages": [clarification],
                "current_phase": "planning",
            }

        mcp_client = self._mcp_client or MCPClient()
        owns_mcp_client = self._mcp_client is None

        try:
            search_input = self._build_search_input(intent, state)
            logger.info(
                f"AccommodationAgent searching hotels in {search_input.city_code} "
                f"from {search_input.check_in} to {search_input.check_out}"
            )
            hotels = await mcp_client.search_hotels(search_input)
            return {
                "hotel_options": hotels,
            }
        except Exception as error:
            wrapped = wrap_agent_error(
                "accommodation_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "planning")},
            )
            return {
                "hotel_options": [],
                "errors": [wrapped.message],
                "messages": [
                    "I couldn't fetch hotel options right now. "
                    "Please confirm your destination and stay dates, then I will try again."
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
    ) -> HotelSearchInput:
        if self._llm is not None:
            user_input = ""
            messages_from_state = state.get("messages")
            if isinstance(messages_from_state, list) and messages_from_state:
                user_input = str(messages_from_state[-1])

            messages = self.build_messages(
                ACCOMMODATION_SYSTEM_PROMPT,
                state={"travel_intent": intent.model_dump(mode="json")},
                user_input=user_input,
            )
            try:
                return self.invoke_structured(messages, HotelSearchInput)
            except AgentExecutionError:
                logger.warning(
                    "LLM accommodation-parameter mapping failed; using deterministic fallback."
                )

        return _build_hotel_search_input(intent)


async def accommodation_node(
    state: Mapping[str, Any],
    *,
    llm: Optional[Any] = None,
    mcp_client: Optional[MCPClient] = None,
) -> dict[str, Any]:
    """LangGraph-compatible accommodation node entrypoint."""
    agent = AccommodationAgent(llm=llm, mcp_client=mcp_client)
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


def _missing_accommodation_fields(intent: TravelIntent) -> list[str]:
    missing: list[str] = []
    if not intent.destination:
        missing.append("destination")
    if not intent.start_date:
        missing.append("check-in date")
    if not intent.end_date and not intent.duration_days:
        missing.append("trip end date or duration")
    return missing


def _build_hotel_search_input(intent: TravelIntent) -> HotelSearchInput:
    check_in = intent.start_date or ""
    check_out = _resolve_check_out(intent.start_date, intent.end_date, intent.duration_days)
    if check_out is None:
        check_out = (date.fromisoformat(check_in) + timedelta(days=1)).isoformat()

    nights = _trip_nights(check_in, check_out)
    return HotelSearchInput(
        city_code=_resolve_city_code(intent.destination or ""),
        check_in=check_in,
        check_out=check_out,
        adults=max(1, int(intent.num_travelers)),
        max_results=5,
        price_range=_resolve_price_range(intent, nights),
        currency=intent.currency or "USD",
    )


def _resolve_check_out(
    start_date: Optional[str],
    end_date: Optional[str],
    duration_days: Optional[int],
) -> Optional[str]:
    if end_date:
        return end_date
    if not start_date or not duration_days:
        return None
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        return None
    return (start + timedelta(days=duration_days)).isoformat()


def _trip_nights(check_in: str, check_out: str) -> int:
    try:
        start = date.fromisoformat(check_in)
        end = date.fromisoformat(check_out)
        return max(1, (end - start).days)
    except ValueError:
        return 1


def _resolve_price_range(intent: TravelIntent, nights: int) -> Optional[PriceRange]:
    if intent.travel_style == TravelStyle.BUDGET:
        return PriceRange.BUDGET
    if intent.travel_style == TravelStyle.MID_RANGE:
        return PriceRange.MID
    if intent.travel_style == TravelStyle.LUXURY:
        return PriceRange.LUXURY

    if intent.budget <= 0:
        return None

    # Uses the same USD tier heuristic defined in M6.
    nightly_per_traveler = intent.budget / max(1, nights * max(intent.num_travelers, 1))
    if nightly_per_traveler < 100:
        return PriceRange.BUDGET
    if nightly_per_traveler <= 300:
        return PriceRange.MID
    return PriceRange.LUXURY


def _resolve_city_code(destination: str) -> str:
    cleaned = destination.strip()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    lowered = cleaned.lower()
    for city, code in _CITY_TO_CODE.items():
        if city in lowered:
            return code

    first_token = cleaned.split(",")[0].strip()
    letters = "".join(ch for ch in first_token.upper() if ch.isalpha())
    if len(letters) >= 3:
        return letters[:3]
    return "UNK"


__all__ = [
    "AccommodationAgent",
    "accommodation_node",
]
