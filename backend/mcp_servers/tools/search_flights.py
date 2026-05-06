"""
Flight search tool for the PLANIT MCP server.

Uses AeroDataBox to fetch real departure schedules for a given origin airport
and date, then filters by destination and estimates ticket prices from duration.
Falls back to mock data when the API key is not configured or no direct flights
are found for the requested route.
"""

from datetime import datetime, timedelta
from typing import Any

from backend.mcp_servers.utils.aerodatabox_client import get_aerodatabox_client
from backend.mcp_servers.utils.mock_data import MOCK_FLIGHTS
from backend.schemas.transport import FlightOption, FlightSearchInput
from backend.utils.logger import get_logger

logger = get_logger("mcp.tools.search_flights")

# Duration buckets → estimated one-way economy price in USD.
# Thresholds are upper bounds in hours.
_PRICE_TIERS: list[tuple[float, float]] = [
    (2.0,  120.0),          # short haul  < 2 h  → $120
    (5.0,  380.0),          # medium haul < 5 h  → $380
    (10.0, 680.0),          # long haul   < 10 h → $680
    (float("inf"), 1050.0), # ultra long  ≥ 10 h → $1050
]


async def search_flights_tool(input_params: FlightSearchInput) -> list[FlightOption]:
    """
    Search for flight options between two airports.

    Live data path (AeroDataBox configured):
    1. Fetch all departures from origin airport for the full requested day
       (two concurrent 12-hour window calls — API limit is 12 h per call).
    2. Filter flights whose arrival airport matches the requested destination.
    3. Map each match to a FlightOption; estimate price from flight duration.

    Mock data path (no API key, or no direct flights found):
    Returns a set of generic mock flights with the requested route applied.

    Args:
        input_params: Validated FlightSearchInput (IATA codes, date, limits).

    Returns:
        List of FlightOption objects, at most input_params.max_results items.
    """
    client = get_aerodatabox_client()

    if client.mock_mode:
        logger.info(
            f"search_flights [{input_params.origin}→{input_params.destination}] "
            f"— AeroDataBox not configured, returning mock data"
        )
        return _mock_flights(input_params)

    logger.info(
        f"search_flights [{input_params.origin}→{input_params.destination}] "
        f"on {input_params.departure_date} — calling AeroDataBox"
    )

    try:
        all_departures = await client.get_full_day_departures(
            iata_code=input_params.origin,
            date=input_params.departure_date,
        )
    except Exception as e:
        logger.warning(f"AeroDataBox call failed — falling back to mock data: {e}")
        return _mock_flights(input_params)

    # Filter: only keep flights heading to the requested destination
    dest_upper = input_params.destination.upper()
    matching = [f for f in all_departures if _arrival_iata(f) == dest_upper]

    logger.info(
        f"{len(all_departures)} total departures from {input_params.origin}, "
        f"{len(matching)} go to {input_params.destination}"
    )

    if not matching:
        logger.info("No direct flights found in AeroDataBox — returning mock data")
        return _mock_flights(input_params)

    if matching:
        logger.debug(f"First matched AeroDataBox record keys: {list(matching[0].keys())}")
        logger.debug(f"First matched AeroDataBox record: {matching[0]}")

    options: list[FlightOption] = []
    for raw in matching[: input_params.max_results]:
        option = _to_flight_option(raw, input_params)
        if option is not None:
            options.append(option)

    if not options:
        logger.warning(
            f"Matched {len(matching)} AeroDataBox flight(s) but none parsed — "
            f"falling back to mock data. Check DEBUG logs for raw record structure."
        )
        return _mock_flights(input_params)

    logger.info(f"Returning {len(options)} flight options from AeroDataBox")
    return options


# ── Helpers ──────────────────────────────────────────────────────────────

def _arrival_iata(flight: dict[str, Any]) -> str:
    """Extract arrival airport IATA code from a withLeg=true flight record."""
    arrival = flight.get("arrival") or {}
    airport = arrival.get("airport") or {}
    return (airport.get("iata") or "").upper()


def _to_flight_option(
    raw: dict[str, Any],
    params: FlightSearchInput,
) -> FlightOption | None:
    """Map a raw AeroDataBox departure record to a FlightOption."""
    # AeroDataBox uses "movement" for the departure leg (some versions use "departure").
    # Times are nested under scheduledTime.utc / scheduledTime.local (not flat fields).
    movement = raw.get("movement") or raw.get("departure") or {}
    arrival = raw.get("arrival") or {}

    dep_time: str = _scheduled_time(movement)
    arr_time: str = _scheduled_time(arrival)

    if not dep_time:
        return None

    origin_iata = (movement.get("airport") or {}).get("iata") or params.origin
    dest_iata = (arrival.get("airport") or {}).get("iata") or params.destination

    airline_info = raw.get("airline") or {}
    airline_name = (
        airline_info.get("name")
        or airline_info.get("iata")
        or "Unknown Airline"
    )

    duration_str, price = _duration_and_price(dep_time, arr_time)

    try:
        return FlightOption(
            airline=airline_name,
            flight_number=raw.get("number") or "",
            origin=origin_iata.upper(),
            destination=dest_iata.upper(),
            departure_time=dep_time,
            arrival_time=arr_time,
            duration=duration_str,
            price=price,
            currency=params.currency,
            stops=0,
            cabin_class="ECONOMY (estimated price)",
        )
    except Exception as e:
        logger.warning(f"Failed to build FlightOption from AeroDataBox record: {e}")
        return None


def _scheduled_time(leg: dict[str, Any]) -> str:
    """Extract scheduled time from an AeroDataBox movement/arrival leg.

    AeroDataBox nests times as: scheduledTime.utc / scheduledTime.local
    UTC is preferred so departure and arrival are always in the same timezone,
    making duration arithmetic in _duration_and_price reliable.
    """
    scheduled = leg.get("scheduledTime") or {}
    return scheduled.get("utc") or scheduled.get("local") or ""


def _duration_and_price(dep_time: str, arr_time: str) -> tuple[str, float]:
    """
    Compute ISO-8601 duration string and estimated price from departure / arrival times.

    Returns ("PT0H00M", 350.0) if either time is missing or unparseable.
    """
    if not dep_time or not arr_time:
        return "PT0H00M", 350.0

    try:
        dep_dt = datetime.fromisoformat(dep_time)
        arr_dt = datetime.fromisoformat(arr_time)
        if arr_dt < dep_dt:          # overnight flight
            arr_dt += timedelta(days=1)

        total_seconds = (arr_dt - dep_dt).total_seconds()
        hours = total_seconds / 3600
        h = int(hours)
        m = int((hours - h) * 60)
        duration_str = f"PT{h}H{m:02d}M"

        price = next(p for threshold, p in _PRICE_TIERS if hours < threshold)
        return duration_str, price

    except Exception as e:
        logger.debug(f"Duration/price estimation failed ({dep_time}, {arr_time}): {e}")
        return "PT0H00M", 350.0


def _mock_flights(params: FlightSearchInput) -> list[FlightOption]:
    """
    Return mock flights with the requested origin/destination/currency/date applied.
    Used when AeroDataBox is not configured or returns no direct flights.
    """
    options: list[FlightOption] = []
    for raw in MOCK_FLIGHTS[: params.max_results]:
        try:
            # Preserve time-of-day but shift both times to the requested travel date.
            # Track overnight offset so arrival stays after departure.
            raw_dep_dt = datetime.fromisoformat(raw["departure_time"])
            raw_arr_dt = datetime.fromisoformat(raw["arrival_time"])
            arr_day_offset = (raw_arr_dt.date() - raw_dep_dt.date()).days

            dep_time = _rebase_time(raw["departure_time"], params.departure_date)
            arr_time = _rebase_time(raw["arrival_time"], params.departure_date, arr_day_offset)

            options.append(
                FlightOption(
                    airline=raw["airline"],
                    flight_number=raw["flight_number"],
                    origin=params.origin,
                    destination=params.destination,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration=raw.get("duration", ""),
                    price=float(raw["price"]),
                    currency=params.currency,
                    stops=int(raw.get("stops", 0)),
                    cabin_class=raw.get("cabin_class"),
                )
            )
        except Exception as e:
            logger.warning(f"Skipping malformed mock flight record: {e}")
    return options


def _rebase_time(time_str: str, date_str: str, extra_days: int = 0) -> str:
    """Shift the date part of a datetime string to date_str + extra_days, keeping the time."""
    try:
        dt = datetime.fromisoformat(time_str)
        base = datetime.fromisoformat(date_str).date() + timedelta(days=extra_days)
        return dt.replace(year=base.year, month=base.month, day=base.day).isoformat()
    except Exception:
        return time_str
