"""
Hotel search tool for the PLANIT MCP server.

Uses the Booking.com API (via RapidAPI) to fetch real hotel listings.
Falls back to mock data when the API key is not configured, when
dest_id resolution fails, or on any API error.
"""

from __future__ import annotations

import re
from typing import Any

from backend.mcp_servers.utils.booking_com_client import get_booking_com_client
from backend.mcp_servers.utils.mock_data import MOCK_HOTELS
from backend.schemas.accommodation import HotelOption, HotelSearchInput, PriceRange
from backend.utils.helpers import calculate_duration
from backend.utils.logger import get_logger

logger = get_logger("mcp.tools.search_hotels")

# PriceRange → (price_min, price_max) in USD per night
_PRICE_RANGE_FILTERS: dict[PriceRange, tuple[int, int]] = {
    PriceRange.BUDGET: (0, 100),
    PriceRange.MID: (100, 300),
    PriceRange.LUXURY: (300, 0),  # 0 max = no upper bound
}


async def search_hotels_tool(input_params: HotelSearchInput) -> list[HotelOption]:
    """
    Search for hotel options in a city for the requested dates.

    Live data path (Booking.com configured):
    1. Resolve city_code → Booking.com dest_id (hardcoded dict or API fallback).
    2. Call /api/v1/hotels/searchHotels with date + guest + currency params.
    3. Parse each hotel record → HotelOption (with price_per_night, rating, amenities).
    4. Apply price_range filter if requested.

    Mock data path (no API key, dest_id not found, or API error):
    Returns generic mock hotels with the requested city/currency applied.

    Args:
        input_params: Validated HotelSearchInput.

    Returns:
        List of HotelOption objects, at most input_params.max_results items.
    """
    client = get_booking_com_client()

    if client.mock_mode:
        logger.info(
            f"search_hotels [{input_params.city_code}] — "
            "Booking.com not configured, returning mock data"
        )
        return _mock_hotels(input_params)

    logger.info(
        f"search_hotels [{input_params.city_code}] "
        f"{input_params.check_in}→{input_params.check_out} — calling Booking.com"
    )

    try:
        nights = _compute_nights(input_params.check_in, input_params.check_out)
        price_min, price_max = _price_filters(input_params.price_range)

        raw_hotels = await client.search_hotels(
            city_name=input_params.city_code,
            arrival_date=input_params.check_in,
            departure_date=input_params.check_out,
            adults=input_params.adults,
            currency=input_params.currency,
            price_min=price_min,
            price_max=price_max,
            max_results=input_params.max_results * 2,  # over-fetch for post-filter
        )
    except Exception as e:
        logger.warning(f"Booking.com call failed — falling back to mock data: {e}")
        return _mock_hotels(input_params)

    if not raw_hotels:
        logger.info("Booking.com returned no hotels — using mock data")
        return _mock_hotels(input_params)

    options: list[HotelOption] = []
    for raw in raw_hotels:
        option = _to_hotel_option(raw, input_params, nights)
        if option is None:
            continue
        # Secondary price range filter (in case API filter wasn't precise)
        if input_params.price_range and not _in_price_range(
            option.price_per_night, input_params.price_range
        ):
            continue
        options.append(option)
        if len(options) >= input_params.max_results:
            break

    if not options:
        logger.info("No hotels passed filters — falling back to mock data")
        return _mock_hotels(input_params)

    logger.info(f"Returning {len(options)} hotel options from Booking.com")
    return options


# ── Response parsing ─────────────────────────────────────────────────────

def _to_hotel_option(
    raw: dict[str, Any],
    params: HotelSearchInput,
    nights: int,
) -> HotelOption | None:
    """
    Map a raw Booking.com hotel record to a HotelOption.

    Booking.com hotel record structure (booking-com15 API):
    {
      "hotel_id": 10679861,
      "accessibilityLabel": "...",
      "property": {
        "name": "...",
        "reviewScore": 8.5,
        "reviewScoreWord": "Very Good",
        "reviewCount": 1518,
        "priceBreakdown": {
          "grossPrice": {"value": 329.0, "currency": "AED"},
          "taxesAndCharges": {"value": 98.0, "currency": "AED"}
        },
        "propertyClass": 5,
        "photoUrls": ["..."],
        "latitude": 19.09,
        "longitude": 72.86,
        "countryCode": "in",
        "wishlistName": "Mumbai",
        "checkin": {"fromTime": "14:00"},
        "checkout": {"untilTime": "12:00"}
      }
    }
    """
    prop = raw.get("property") or {}
    label = raw.get("accessibilityLabel") or ""

    # Name
    name = prop.get("name") or _parse_label_name(label)
    if not name:
        return None

    # Review score (0–10 from Booking.com → we keep as-is, max 10)
    review_score = _safe_float(prop.get("reviewScore")) or _parse_label_score(label)
    # Normalise to 0–5 scale expected by HotelOption
    rating = round(review_score / 2.0, 1) if review_score else 0.0

    # Star class (0–5)
    star_class = _safe_int(prop.get("propertyClass")) or _parse_label_stars(label) or 0

    # Pricing
    breakdown = prop.get("priceBreakdown") or {}
    gross = breakdown.get("grossPrice") or {}
    total_price = _safe_float(gross.get("value")) or _parse_label_price(label)
    currency = (gross.get("currency") or params.currency).upper()
    price_per_night = round(total_price / max(nights, 1), 2) if total_price else 0.0

    # Address / city
    city_name = (
        prop.get("wishlistName")
        or (prop.get("location") or {}).get("city")
        or params.city_code
    )
    address = _build_address(prop, city_name)

    # Amenities from star class + review word
    amenities = _infer_amenities(star_class, prop.get("reviewScoreWord") or "")

    # Photo / URL
    photo_urls: list[str] = prop.get("photoUrls") or []
    source_url = photo_urls[0] if photo_urls else None

    try:
        return HotelOption(
            name=name,
            hotel_id=str(raw.get("hotel_id") or ""),
            address=address,
            city=city_name,
            rating=rating,
            price_per_night=price_per_night,
            total_price=round(price_per_night * nights, 2),
            currency=currency,
            amenities=amenities,
            source_url=source_url,
        )
    except Exception as e:
        logger.warning(f"Failed to build HotelOption for '{name}': {e}")
        return None


# ── Label parsers (fallback when property fields are absent) ─────────────

def _parse_label_name(label: str) -> str:
    """Extract hotel name from accessibilityLabel (first sentence / comma segment)."""
    if not label:
        return ""
    return label.split(".")[0].split(",")[0].strip()


def _parse_label_score(label: str) -> float:
    """Extract review score like '8.5' from accessibilityLabel."""
    m = re.search(r"\b(\d+\.\d+)\s+\w+\s+\d+\s+review", label, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_label_stars(label: str) -> int:
    """Extract star count like '5 out of 5 stars' from accessibilityLabel."""
    m = re.search(r"(\d+)\s+out of \d+\s+star", label, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _parse_label_price(label: str) -> float:
    """Extract current price from 'Current price NNN AED' in accessibilityLabel."""
    m = re.search(r"[Cc]urrent price\s+(\d[\d,\.]*)", label)
    if m:
        return float(m.group(1).replace(",", ""))
    # Try any currency-prefixed number
    m2 = re.search(r"(?:USD|AED|EUR|GBP|INR|₹|\$|€|£)\s*(\d[\d,\.]*)", label)
    if m2:
        return float(m2.group(1).replace(",", ""))
    return 0.0


# ── Helpers ──────────────────────────────────────────────────────────────

def _build_address(prop: dict[str, Any], city: str) -> str:
    parts: list[str] = []
    loc = prop.get("location") or {}
    street = loc.get("address") or loc.get("street") or ""
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    country = prop.get("countryCode") or ""
    if country:
        parts.append(country.upper())
    return ", ".join(parts) if parts else city


def _infer_amenities(stars: int, score_word: str) -> list[str]:
    """Infer likely amenities from star class and review score word."""
    base = ["Free WiFi"]
    if stars >= 3:
        base += ["Air conditioning", "24-hour reception"]
    if stars >= 4:
        base += ["Restaurant", "Fitness center", "Concierge"]
    if stars >= 5:
        base += ["Spa", "Pool", "Room service", "Valet parking"]
    if score_word.lower() in ("exceptional", "superb", "fabulous"):
        if "Spa" not in base:
            base.append("Spa")
    return base


def _compute_nights(check_in: str, check_out: str) -> int:
    try:
        return max(1, calculate_duration(check_in, check_out))
    except Exception:
        return 1


def _price_filters(price_range: PriceRange | None) -> tuple[int, int]:
    if price_range is None:
        return 0, 0
    return _PRICE_RANGE_FILTERS.get(price_range, (0, 0))


def _in_price_range(price_per_night: float, range_type: PriceRange) -> bool:
    if range_type == PriceRange.BUDGET:
        return price_per_night < 100
    if range_type == PriceRange.MID:
        return 100 <= price_per_night <= 300
    if range_type == PriceRange.LUXURY:
        return price_per_night > 300
    return True


def _safe_float(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _mock_hotels(params: HotelSearchInput) -> list[HotelOption]:
    """Return mock hotels with the requested city/currency applied."""
    nights = _compute_nights(params.check_in, params.check_out)
    options: list[HotelOption] = []

    for raw in MOCK_HOTELS[: params.max_results]:
        try:
            price_per_night = float(raw["price_per_night"])
            if params.price_range and not _in_price_range(price_per_night, params.price_range):
                continue
            options.append(
                HotelOption(
                    name=raw["name"],
                    hotel_id=raw.get("hotel_id"),
                    address=raw.get("address", ""),
                    city=params.city_code,
                    rating=float(raw.get("rating", 0)),
                    price_per_night=price_per_night,
                    total_price=price_per_night * nights,
                    currency=params.currency,
                    amenities=raw.get("amenities", []),
                    source_url=raw.get("source_url"),
                )
            )
        except Exception as e:
            logger.warning(f"Skipping malformed mock hotel record: {e}")

    return options
