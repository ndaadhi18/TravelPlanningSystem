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

# Fast-path hardcoded dict for common cities.
# AeroDataBox airport search is used as fallback for anything not listed here.
_CITY_TO_IATA: dict[str, str] = {
    "mumbai": "BOM",
    "bombay": "BOM",
    "delhi": "DEL",
    "new delhi": "DEL",
    "paris": "CDG",
    "london": "LHR",
    "new york": "JFK",
    "new york city": "JFK",
    "san francisco": "SFO",
    "tokyo": "HND",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA",
    "singapore": "SIN",
    "dubai": "DXB",
    "bangkok": "BKK",
    "amsterdam": "AMS",
    "frankfurt": "FRA",
    "sydney": "SYD",
    "toronto": "YYZ",
    "los angeles": "LAX",
    "chicago": "ORD",
    "miami": "MIA",
    "seattle": "SEA",
    "boston": "BOS",
    "rome": "FCO",
    "milan": "MXP",
    "madrid": "MAD",
    "barcelona": "BCN",
    "istanbul": "IST",
    "beijing": "PEK",
    "shanghai": "PVG",
    "hong kong": "HKG",
    "kuala lumpur": "KUL",
    "jakarta": "CGK",
    "cairo": "CAI",
    "johannesburg": "JNB",
    "nairobi": "NBO",
    "mexico city": "MEX",
    "sao paulo": "GRU",
    "buenos aires": "EZE",
    "kolkata": "CCU",
    "pune": "PNQ",
    "ahmedabad": "AMD",
    "goa": "GOI",
    "kochi": "COK",
    "jaipur": "JAI",
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
            return {
                "flight_options": [],
                "messages": [build_transport_clarification(
                    ["departure city", "destination", "departure date"]
                )],
                "current_phase": "planning",
            }

        missing_fields = _missing_transport_fields(intent)
        if missing_fields:
            return {
                "flight_options": [],
                "messages": [build_transport_clarification(missing_fields)],
                "current_phase": "planning",
            }

        mcp_client = self._mcp_client or MCPClient()
        owns_mcp_client = self._mcp_client is None

        try:
            search_input = await self._build_search_input(intent, state)
            logger.info(
                f"TransportAgent searching flights {search_input.origin} -> "
                f"{search_input.destination} on {search_input.departure_date}"
            )
            flights = await mcp_client.search_flights(search_input)
            return {"flight_options": flights}

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

    async def _build_search_input(
        self,
        intent: TravelIntent,
        state: Mapping[str, Any],
    ) -> FlightSearchInput:
        """Build FlightSearchInput, resolving city names to IATA codes."""
        if self._llm is not None:
            user_input = ""
            messages_from_state = state.get("messages")
            if isinstance(messages_from_state, list) and messages_from_state:
                user_input = str(messages_from_state[-1])

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

        return await _build_flight_search_input(intent)


async def transport_node(
    state: Mapping[str, Any],
    *,
    llm: Optional[Any] = None,
    mcp_client: Optional[MCPClient] = None,
) -> dict[str, Any]:
    """LangGraph-compatible transport node entrypoint."""
    agent = TransportAgent(llm=llm, mcp_client=mcp_client)
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


def _missing_transport_fields(intent: TravelIntent) -> list[str]:
    missing: list[str] = []
    if not intent.source_location:
        missing.append("departure city")
    if not intent.destination:
        missing.append("destination")
    if not intent.start_date:
        missing.append("departure date")
    return missing


# ── IATA resolution ──────────────────────────────────────────────────────

def _resolve_iata_sync(value: str) -> str | None:
    """
    Fast synchronous resolution: already-valid IATA code or hardcoded dict.

    Returns the 3-letter IATA code, or None if not found (triggers API fallback).
    """
    cleaned = value.strip()

    # Already looks like an IATA code
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    # Hardcoded city → IATA map
    lowered = cleaned.lower()
    for city, code in _CITY_TO_IATA.items():
        if city in lowered:
            return code

    return None


async def _resolve_iata_async(value: str) -> str:
    """
    Resolve a city/airport name to an IATA code.

    Resolution order:
    1. Fast sync: already a valid 3-letter code, or in _CITY_TO_IATA dict.
    2. AeroDataBox /airports/search/term API (when key is configured).
    3. Last resort: take the first 3 alphabetic characters of the input.
    """
    fast = _resolve_iata_sync(value)
    if fast is not None:
        return fast

    # Try AeroDataBox airport search
    try:
        from backend.mcp_servers.utils.aerodatabox_client import get_aerodatabox_client
        client = get_aerodatabox_client()
        airports = await client.search_airports(value, limit=1, with_flight_info_only=True)
        if airports:
            iata = (airports[0].get("iata") or "").strip().upper()
            if len(iata) == 3:
                logger.info(f"AeroDataBox resolved '{value}' → {iata}")
                return iata
    except Exception as e:
        logger.warning(f"AeroDataBox airport resolution failed for '{value}': {e}")

    # Last resort: derive from the text itself
    letters = "".join(ch for ch in value.upper() if ch.isalpha())
    fallback = letters[:3] if len(letters) >= 3 else "UNK"
    logger.warning(f"IATA resolution failed for '{value}', using fallback '{fallback}'")
    return fallback


# ── Search input builder ─────────────────────────────────────────────────

async def _build_flight_search_input(intent: TravelIntent) -> FlightSearchInput:
    """Build a FlightSearchInput from a TravelIntent using async IATA resolution."""
    origin, destination = await _resolve_both_iata(
        intent.source_location or "",
        intent.destination or "",
    )
    return FlightSearchInput(
        origin=origin,
        destination=destination,
        departure_date=intent.start_date or "",
        return_date=_normalize_return_date(intent.start_date, intent.end_date),
        adults=max(1, int(intent.num_travelers)),
        max_results=5,
        currency=intent.currency or "USD",
    )


async def _resolve_both_iata(origin: str, destination: str) -> tuple[str, str]:
    """Resolve origin and destination concurrently."""
    import asyncio
    return await asyncio.gather(
        _resolve_iata_async(origin),
        _resolve_iata_async(destination),
    )


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
