"""
Booking.com API client via RapidAPI (booking-com15).

Base URL : https://booking-com15.p.rapidapi.com
Auth     : x-rapidapi-key + x-rapidapi-host headers
Env var  : RAPIDAPI_KEY

Rate limit note: this account has ~50 requests. Results are cached per
(dest_id, arrival_date, departure_date) to minimise consumption.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import httpx

from backend.core.settings import get_settings
from backend.mcp_servers.utils.error_handler import ErrorCode, MCPToolError
from backend.utils.logger import get_logger

logger = get_logger("mcp.booking_com")

_BASE_URL = "https://booking-com15.p.rapidapi.com"
_RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"

# ── Static city → Booking.com dest_id map ────────────────────────────────
# dest_id is Booking.com's internal numeric city identifier.
# Negative values are city-level IDs (search_type="CITY").
# Anything not here falls back to the /searchDestination API call.

_CITY_TO_DEST_ID: dict[str, str] = {
    # India
    "mumbai": "-2092174",
    "bombay": "-2092174",
    "delhi": "-2106102",
    "new delhi": "-2106102",
    "bangalore": "-2090174",
    "bengaluru": "-2090174",
    "hyderabad": "-2091116",
    "chennai": "-2090970",
    "kolkata": "-2091072",
    "pune": "-2091231",
    "goa": "-2085748",
    "jaipur": "-2090634",
    "kochi": "-2090822",
    "ahmedabad": "-2090017",
    # Europe
    "paris": "-1456928",
    "london": "-2601889",
    "rome": "-126693",
    "amsterdam": "-2140479",
    "barcelona": "-372490",
    "madrid": "-390625",
    "berlin": "-1746443",
    "milan": "-132008",
    "vienna": "-1995499",
    "prague": "-553173",
    "budapest": "-850553",
    "lisbon": "-2167973",
    "athens": "-814876",
    # Middle East & Asia
    "dubai": "-782831",
    "abu dhabi": "-782832",
    "istanbul": "-755070",
    "singapore": "-73635",
    "bangkok": "-3077928",
    "tokyo": "-246227",
    "osaka": "-240905",
    "kuala lumpur": "-3301580",
    "hong kong": "-1353149",
    "beijing": "-2014661",
    "shanghai": "-2030827",
    "bali": "-1126984",
    # Americas
    "new york": "20088325",
    "new york city": "20088325",
    "los angeles": "20044342",
    "san francisco": "20015732",
    "miami": "20010589",
    "chicago": "20033173",
    "toronto": "20015654",
    "mexico city": "-1658378",
    # Oceania & Africa
    "sydney": "-1603135",
    "melbourne": "-1603197",
    "nairobi": "-717992",
    "cairo": "-290691",
    "johannesburg": "-1217214",
}


class BookingComClient:
    """
    Async HTTP client for Booking.com hotel search via RapidAPI.

    Uses a two-level dest_id resolution:
    1. Fast: hardcoded _CITY_TO_DEST_ID dict (no API call).
    2. Fallback: /api/v1/hotels/searchDestination API call (costs 1 request).

    Results are cached in-memory per search key to protect the 50-request quota.
    """

    # Simple in-process cache: (dest_id, arrival, departure) → list[dict]
    _result_cache: dict[tuple[str, str, str, int, str], list[dict[str, Any]]] = {}
    # dest_id cache: city_name → (dest_id, search_type)
    _dest_id_cache: dict[str, tuple[str, str]] = {}

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = self._settings.rapidapi_key or ""
        self.mock_mode = not self._settings.booking_com_configured

        if self.mock_mode:
            logger.warning(
                "RAPIDAPI_KEY not configured — hotel search will use mock data. "
                "Set RAPIDAPI_KEY in .env for real Booking.com hotel data."
            )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-rapidapi-key": self._api_key,
            "x-rapidapi-host": _RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }

    # ── Destination resolution ───────────────────────────────────────────

    async def resolve_dest_id(self, city_name: str) -> tuple[str, str]:
        """
        Resolve a city name to a Booking.com (dest_id, search_type) pair.

        Resolution order:
        1. Hardcoded _CITY_TO_DEST_ID dict — zero API calls.
        2. In-process cache from previous API lookups.
        3. /api/v1/hotels/searchDestination API call.

        Returns ("", "") if resolution fails completely.
        """
        lowered = city_name.strip().lower()

        # 1. Static dict
        if lowered in _CITY_TO_DEST_ID:
            return _CITY_TO_DEST_ID[lowered], "CITY"

        # Check sub-string match (e.g. "Paris, France" → "paris")
        for city, dest_id in _CITY_TO_DEST_ID.items():
            if city in lowered:
                return dest_id, "CITY"

        # 2. In-process cache
        if lowered in self._dest_id_cache:
            return self._dest_id_cache[lowered]

        # 3. API fallback
        result = await self._search_destination_api(city_name)
        if result[0]:
            self._dest_id_cache[lowered] = result
        return result

    async def _search_destination_api(self, query: str) -> tuple[str, str]:
        """Call searchDestination to look up dest_id for an unknown city."""
        if self.mock_mode:
            return "", ""

        logger.info(f"BookingCom: resolving dest_id for '{query}' via searchDestination API")
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(
                    f"{_BASE_URL}/api/v1/hotels/searchDestination",
                    headers=self._headers,
                    params={"query": query},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", [])
                if not items:
                    logger.warning(f"searchDestination returned no results for '{query}'")
                    return "", ""

                # Prefer the first city-type result
                for item in items:
                    dest_type = (item.get("dest_type") or item.get("search_type") or "").upper()
                    if dest_type in ("CITY", "DISTRICT", "REGION"):
                        dest_id = str(item.get("dest_id", ""))
                        if dest_id:
                            logger.info(f"Resolved '{query}' → dest_id={dest_id}, type={dest_type}")
                            return dest_id, dest_type

                # Fallback: take whatever the first result is
                first = items[0]
                dest_id = str(first.get("dest_id", ""))
                dest_type = (first.get("dest_type") or first.get("search_type") or "CITY").upper()
                return dest_id, dest_type

            except Exception as e:
                logger.warning(f"searchDestination API call failed for '{query}': {e}")
                return "", ""

    # ── Hotel search ─────────────────────────────────────────────────────

    async def search_hotels(
        self,
        city_name: str,
        arrival_date: str,
        departure_date: str,
        adults: int = 1,
        currency: str = "USD",
        price_min: int = 0,
        price_max: int = 0,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search hotels in a city for specific dates.

        Args:
            city_name    : City name (resolved to dest_id internally).
            arrival_date : Check-in date "YYYY-MM-DD".
            departure_date: Check-out date "YYYY-MM-DD".
            adults       : Number of adult guests.
            currency     : ISO currency code, e.g. "USD".
            price_min    : Min price filter per night (0 = no filter).
            price_max    : Max price filter per night (0 = no filter).
            max_results  : Maximum hotels to return.

        Returns:
            List of raw hotel dicts from Booking.com response.
        """
        dest_id, search_type = await self.resolve_dest_id(city_name)
        if not dest_id:
            logger.warning(f"Could not resolve dest_id for '{city_name}' — no hotel results")
            return []

        # Check in-memory cache first (protect the 50-request quota)
        cache_key = (dest_id, arrival_date, departure_date, adults, currency)
        if cache_key in self._result_cache:
            logger.info(f"BookingCom: cache hit for {city_name} {arrival_date}→{departure_date}")
            return self._result_cache[cache_key][:max_results]

        logger.info(
            f"BookingCom: searching hotels in '{city_name}' (dest_id={dest_id}) "
            f"{arrival_date}→{departure_date}, adults={adults}, currency={currency}"
        )

        params: dict[str, Any] = {
            "dest_id": dest_id,
            "search_type": search_type,
            "arrival_date": arrival_date,
            "departure_date": departure_date,
            "adults": str(adults),
            "room_qty": "1",
            "page_number": "1",
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": currency.upper(),
            "location": "US",
        }
        if price_min > 0:
            params["price_min"] = str(price_min)
        if price_max > 0:
            params["price_max"] = str(price_max)

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(
                    f"{_BASE_URL}/api/v1/hotels/searchHotels",
                    headers=self._headers,
                    params=params,
                )
                resp.raise_for_status()
                body = resp.json()

                hotels = (
                    body.get("data", {}).get("hotels")
                    or body.get("data", [])
                    or []
                )
                if not isinstance(hotels, list):
                    hotels = []

                logger.info(f"BookingCom returned {len(hotels)} hotels for '{city_name}'")

                # Cache for the life of this process
                self._result_cache[cache_key] = hotels
                return hotels[:max_results]

            except httpx.HTTPStatusError as e:
                snippet = e.response.text[:300]
                logger.error(
                    f"BookingCom HTTP {e.response.status_code} for '{city_name}': {snippet}"
                )
                raise MCPToolError(
                    message=f"Booking.com returned HTTP {e.response.status_code}",
                    code=ErrorCode.API_ERROR,
                    details={"status": e.response.status_code, "body": snippet},
                )
            except httpx.TimeoutException:
                raise MCPToolError(
                    message="Booking.com request timed out after 20 s",
                    code=ErrorCode.TIMEOUT,
                )
            except MCPToolError:
                raise
            except Exception as e:
                raise MCPToolError(
                    message=f"Booking.com request failed: {e}",
                    code=ErrorCode.API_ERROR,
                )


@lru_cache(maxsize=1)
def get_booking_com_client() -> BookingComClient:
    """Singleton Booking.com client (created once per process)."""
    return BookingComClient()
