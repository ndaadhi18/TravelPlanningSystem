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
            return {
                "hotel_options": [],
                "messages": [build_accommodation_clarification(
                    ["destination", "check-in date", "trip end date or duration"]
                )],
                "current_phase": "planning",
            }

        missing_fields = _missing_accommodation_fields(intent)
        if missing_fields:
            return {
                "hotel_options": [],
                "messages": [build_accommodation_clarification(missing_fields)],
                "current_phase": "planning",
            }

        mcp_client = self._mcp_client or MCPClient()
        owns_mcp_client = self._mcp_client is None

        try:
            search_input = await self._build_search_input(intent, state)
            logger.info(
                f"AccommodationAgent searching hotels in '{search_input.city_code}' "
                f"from {search_input.check_in} to {search_input.check_out}"
            )
            hotels = await mcp_client.search_hotels(search_input)
            return {"hotel_options": hotels}

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

    async def _build_search_input(
        self,
        intent: TravelIntent,
        state: Mapping[str, Any],
    ) -> HotelSearchInput:
        """Build HotelSearchInput. Tries LLM first, falls back to deterministic."""
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


# ── Intent helpers ───────────────────────────────────────────────────────

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


# ── Search input builder ─────────────────────────────────────────────────

def _build_hotel_search_input(intent: TravelIntent) -> HotelSearchInput:
    """
    Build HotelSearchInput from TravelIntent.

    city_code is passed as the destination name (e.g. "Paris") rather than
    a 3-letter IATA-style code, because Booking.com resolves by city name.
    The MCP tool / BookingComClient handles dest_id resolution internally.
    """
    check_in = intent.start_date or ""
    check_out = _resolve_check_out(intent.start_date, intent.end_date, intent.duration_days)
    if check_out is None and check_in:
        check_out = (date.fromisoformat(check_in) + timedelta(days=1)).isoformat()
    check_out = check_out or ""

    nights = _trip_nights(check_in, check_out)

    # Use the first part of the destination (before comma) as the city name
    destination = intent.destination or ""
    city_name = destination.split(",")[0].strip() or destination

    return HotelSearchInput(
        city_code=city_name,
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

    nightly = intent.budget / max(1, nights * max(intent.num_travelers, 1))
    if nightly < 100:
        return PriceRange.BUDGET
    if nightly <= 300:
        return PriceRange.MID
    return PriceRange.LUXURY


__all__ = [
    "AccommodationAgent",
    "accommodation_node",
]
