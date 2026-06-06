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
from backend.schemas.accommodation import HotelSearchInput, HotelOption, PriceRange
from backend.schemas.travel_intent import TravelIntent, TravelStyle
from backend.services.mcp_client import MCPClient
from backend.utils.logger import get_logger

logger = get_logger("agents.accommodation")

# ── City name → IATA code lookup ────────────────────────────────────────────
_CITY_TO_IATA: dict[str, str] = {
    "mumbai": "BOM", "bombay": "BOM",
    "delhi": "DEL", "new delhi": "DEL",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD", "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU",
    "ahmedabad": "AMD", "pune": "PNQ", "goa": "GOI",
    "jaipur": "JAI", "kochi": "COK", "cochin": "COK",
    "lucknow": "LKO", "bhopal": "BHO", "indore": "IDR",
    "amritsar": "ATQ", "varanasi": "VNS", "agra": "AGR",
    "london": "LON", "paris": "PAR", "new york": "NYC",
    "tokyo": "TYO", "dubai": "DXB", "singapore": "SIN",
    "bangkok": "BKK", "sydney": "SYD", "toronto": "YTO",
    "berlin": "BER", "amsterdam": "AMS", "rome": "ROM",
    "barcelona": "BCN", "madrid": "MAD", "istanbul": "IST",
    "beijing": "BJS", "shanghai": "SHA", "hong kong": "HKG",
    "seoul": "SEL", "osaka": "OSA", "kuala lumpur": "KUL",
    "los angeles": "LAX", "chicago": "CHI", "miami": "MIA",
    "san francisco": "SFO", "mexico city": "MEX",
    "cairo": "CAI", "nairobi": "NBI", "johannesburg": "JNB",
}


def _city_to_iata(city_name: str) -> Optional[str]:
    return _CITY_TO_IATA.get(city_name.lower().strip())


class AccommodationAgent(BaseAgent):
    """Construct hotel search params from intent and fetch hotel options."""

    def __init__(self, *, llm: Optional[Any] = None, mcp_client: Optional[MCPClient] = None):
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
            destination = (intent.destination or "").split(",")[0].strip()
            iata_code = _city_to_iata(destination)

            if iata_code:
                try:
                    # Pass the full city name so Booking.com resolves correctly
                    search_input = _build_hotel_search_input(intent, destination)
                    logger.info(
                        f"AccommodationAgent searching hotels in '{destination}' "
                        f"from {search_input.check_in} to {search_input.check_out}"
                    )
                    hotels = await mcp_client.search_hotels(search_input)
                    if hotels:
                        return {"hotel_options": hotels}
                except Exception as amadeus_err:
                    logger.warning(f"Amadeus hotel search failed: {amadeus_err}. Falling back to Tavily.")

            # ── LLM-powered hotel recommendation fallback ────────────────
            logger.info(f"AccommodationAgent: LLM fallback for hotels in '{destination}'")
            hotel_options = await self._llm_hotel_recommendations(intent, destination)
            return {"hotel_options": hotel_options}

        except Exception as error:
            wrapped = wrap_agent_error("accommodation_agent", "run", error,
                                       context={"current_phase": state.get("current_phase")})
            return {"hotel_options": [], "errors": [wrapped.message], "current_phase": "planning"}
        finally:
            if owns_mcp_client:
                await mcp_client.close()

    async def _llm_hotel_recommendations(
        self, intent: TravelIntent, destination: str,
    ) -> list[HotelOption]:
        """Use LLM to generate realistic hotel recommendations with estimated prices."""
        import json as _json
        import re as _re
        from langchain_core.messages import HumanMessage, SystemMessage

        style = _style_label(intent)
        nights = intent.duration_days or 3
        travelers = max(1, intent.num_travelers)

        # Determine currency
        _INDIAN_CITIES = {
            "mumbai", "bombay", "delhi", "new delhi", "bangalore", "bengaluru",
            "hyderabad", "chennai", "kolkata", "pune", "goa", "jaipur",
            "kochi", "ahmedabad", "lucknow", "varanasi", "agra", "amritsar",
        }
        currency = "INR" if destination.lower().strip() in _INDIAN_CITIES else (intent.currency or "USD")

        system = (
            "You are a travel accommodation expert. Given a destination and budget tier, "
            "recommend 3 real, well-known hotels that actually exist in that city. "
            "Provide realistic estimated price-per-night based on the budget tier and destination.\n\n"
            "Output ONLY valid JSON — no markdown fences, no extra text."
        )

        user = f"""Recommend 3 {style} hotels in {destination} for {travelers} traveller(s) staying {nights} nights.

Currency: {currency}
Budget tier: {style}

Output JSON array:
[
  {{
    "name": "Actual Hotel Name",
    "address": "Neighbourhood or area, {destination}",
    "price_per_night": 3500,
    "rating": 4.2,
    "amenities": ["Free WiFi", "Breakfast", "AC"]
  }}
]

Rules:
- Use REAL hotel names that exist in {destination}. No article titles or listicle headings.
- price_per_night must be a realistic number in {currency} for {style} tier.
- Budget tier guide for INR: budget=1000-3000, moderate=3000-8000, luxury=8000-25000 per night.
- Budget tier guide for USD: budget=30-80, moderate=80-200, luxury=200-600 per night.
- rating: 0-5 scale.
- amenities: 3-5 relevant amenities."""

        if self._llm is None:
            logger.warning("No LLM configured for hotel fallback — using static estimates")
            return _static_hotel_estimates(destination, style, nights, currency)

        try:
            result = self._llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            raw = getattr(result, "content", str(result))

            # Strip markdown fences
            raw = _re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            match = _re.search(r"\[.*\]", raw, _re.DOTALL)
            if not match:
                raise ValueError("LLM returned no valid JSON array for hotels")

            hotels_data = _json.loads(match.group())
            options: list[HotelOption] = []
            for h in hotels_data[:3]:
                ppn = float(h.get("price_per_night", 0))
                options.append(HotelOption(
                    name=h.get("name", "Hotel"),
                    address=h.get("address", destination),
                    city=destination,
                    rating=min(5.0, max(0.0, float(h.get("rating", 0)))),
                    price_per_night=ppn,
                    total_price=round(ppn * nights, 2),
                    currency=currency,
                    amenities=h.get("amenities", []),
                ))

            if options:
                return options

        except Exception as e:
            logger.warning(f"LLM hotel recommendation failed: {e}. Using static estimates.")

        return _static_hotel_estimates(destination, style, nights, currency)

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

        # Note: This fallback path might need an IATA code if called directly.
        # Keeping for legacy compatibility but primarily using the new flow in run().
        destination = (intent.destination or "").split(",")[0].strip()
        iata_code = _city_to_iata(destination) or destination
        return _build_hotel_search_input(intent, iata_code)


async def accommodation_node(
    state: Mapping[str, Any], *, llm: Optional[Any] = None, mcp_client: Optional[MCPClient] = None,
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


def _style_label(intent: TravelIntent) -> str:
    mapping = {
        TravelStyle.BUDGET: "budget-friendly",
        TravelStyle.MID_RANGE: "mid-range",
        TravelStyle.LUXURY: "luxury",
    }
    return mapping.get(intent.travel_style, "good") if intent.travel_style else "good"


# ── Search input builder ─────────────────────────────────────────────────

def _build_hotel_search_input(intent: TravelIntent, city_name: str) -> HotelSearchInput:
    check_in = intent.start_date or ""
    check_out = _resolve_check_out(intent.start_date, intent.end_date, intent.duration_days)
    if check_out is None and check_in:
        check_out = (date.fromisoformat(check_in) + timedelta(days=1)).isoformat()
    check_out = check_out or ""
    nights = _trip_nights(check_in, check_out)

    # Use INR for Indian cities, otherwise the intent's currency or USD
    _INDIAN_CITIES = {
        "mumbai", "bombay", "delhi", "new delhi", "bangalore", "bengaluru",
        "hyderabad", "chennai", "kolkata", "pune", "goa", "jaipur",
        "kochi", "ahmedabad", "lucknow", "varanasi", "agra", "amritsar",
        "indore", "bhopal",
    }
    currency = intent.currency or "USD"
    if city_name.lower().strip() in _INDIAN_CITIES:
        currency = "INR"

    return HotelSearchInput(
        city_code=city_name,
        check_in=check_in,
        check_out=check_out,
        adults=max(1, int(intent.num_travelers)),
        max_results=5,
        price_range=_resolve_price_range(intent, nights),
        currency=currency,
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
        return (date.fromisoformat(start_date) + timedelta(days=duration_days)).isoformat()
    except ValueError:
        return None


def _trip_nights(check_in: str, check_out: str) -> int:
    try:
        return max(1, (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days)
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


def _static_hotel_estimates(
    destination: str, style: str, nights: int, currency: str,
) -> list[HotelOption]:
    """Last-resort static hotel estimates when no LLM or API is available."""
    # Price-per-night estimates by tier and currency
    _PRICE_MAP: dict[str, dict[str, float]] = {
        "budget-friendly": {"INR": 1800.0, "USD": 45.0, "EUR": 40.0, "GBP": 35.0},
        "mid-range":       {"INR": 5500.0, "USD": 120.0, "EUR": 100.0, "GBP": 90.0},
        "luxury":          {"INR": 15000.0, "USD": 350.0, "EUR": 300.0, "GBP": 270.0},
        "good":            {"INR": 4000.0, "USD": 100.0, "EUR": 85.0, "GBP": 75.0},
    }
    tier_prices = _PRICE_MAP.get(style, _PRICE_MAP["good"])
    ppn = tier_prices.get(currency.upper(), tier_prices.get("USD", 100.0))

    _TEMPLATES = [
        {"name": f"{style.title()} Hotel in {destination}", "amenities": ["Free WiFi", "AC", "Restaurant"]},
        {"name": f"City Centre Stay, {destination}", "amenities": ["Free WiFi", "24h Reception", "AC"]},
        {"name": f"{destination} Comfort Inn", "amenities": ["Free WiFi", "Breakfast", "Parking"]},
    ]

    options: list[HotelOption] = []
    for i, tmpl in enumerate(_TEMPLATES):
        per_night = round(ppn * (1 + i * 0.15), 2)  # slight variation
        options.append(HotelOption(
            name=tmpl["name"],
            address=destination,
            city=destination,
            rating=round(3.5 + i * 0.3, 1),
            price_per_night=per_night,
            total_price=round(per_night * nights, 2),
            currency=currency,
            amenities=tmpl["amenities"],
        ))
    return options


__all__ = [
    "AccommodationAgent",
    "accommodation_node",
]
