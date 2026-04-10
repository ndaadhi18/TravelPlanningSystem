"""
Hotel search tool for PLANIT MCP server.

Uses the AmadeusClient to fetch hotel offers in two steps:
1. Search for hotel IDs by city.
2. Search for specific offers/pricing for those IDs for requested dates.
"""

from typing import Any, Optional

from backend.mcp_servers.utils.amadeus_client import get_amadeus_client
from backend.schemas.accommodation import HotelOption, HotelSearchInput, PriceRange
from backend.utils.logger import get_logger

logger = get_logger("mcp.tools.search_hotels")


async def search_hotels_tool(input_params: HotelSearchInput) -> list[HotelOption]:
    """
    Search for hotel offers using the Amadeus API (two-step process).
    
    Args:
        input_params: Structured hotel search parameters.
        
    Returns:
        A list of standardized HotelOption objects.
    """
    logger.info(
        f"MCP Tool 'search_hotels' called: {input_params.city_code} from "
        f"{input_params.check_in} to {input_params.check_out}"
    )

    try:
        client = get_amadeus_client()
        
        # --- Step 1: Search for hotels in the city to get IDs ---
        # We fetch more IDs than requested max_results to account for hotels
        # that might not have availability for the specific dates in Step 2.
        city_search_response = client.search_hotels_by_city(
            city_code=input_params.city_code,
            max_results=min(input_params.max_results * 3, 50),
        )
        
        hotel_data = city_search_response.get("data", [])
        if not hotel_data:
            logger.info(f"No hotels found in city {input_params.city_code}")
            return []
            
        hotel_ids = [hotel["hotelId"] for hotel in hotel_data if "hotelId" in hotel]
        logger.debug(f"Found {len(hotel_ids)} hotel IDs for city {input_params.city_code}")

        # --- Step 2: Search for offers for those hotel IDs ---
        # Amadeus typically allows searching up to 20 hotel IDs at once.
        # We'll take the first 20 IDs.
        target_hotel_ids = hotel_ids[:20]
        
        offers_response = client.search_hotel_offers(
            hotel_ids=target_hotel_ids,
            check_in=input_params.check_in,
            check_out=input_params.check_out,
            adults=input_params.adults,
            currency=input_params.currency,
        )
        
        offer_data = offers_response.get("data", [])
        hotel_options = []

        for item in offer_data:
            try:
                hotel_info = item.get("hotel", {})
                offers = item.get("offers", [])
                
                if not offers:
                    continue
                    
                # Take the first available offer
                primary_offer = offers[0]
                price_info = primary_offer.get("price", {})
                
                # Extract price values
                total_price = float(price_info.get("total", 0.0))
                
                # Get average price per night (Amadeus usually provides this)
                avg_price = price_info.get("variations", {}).get("average", {}).get("base")
                if avg_price:
                    price_per_night = float(avg_price)
                else:
                    # Fallback: simple division if average not available
                    # (Though this is rare in Amadeus hotel offers)
                    from backend.utils.helpers import calculate_duration
                    try:
                        nights = calculate_duration(input_params.check_in, input_params.check_out)
                        price_per_night = total_price / max(nights, 1)
                    except Exception:
                        price_per_night = total_price

                # Filter by price range if requested
                if input_params.price_range:
                    if not _is_in_price_range(price_per_night, input_params.price_range, input_params.currency):
                        continue

                # Format address
                address_obj = hotel_info.get("address", {})
                lines = address_obj.get("lines", [])
                city = address_obj.get("cityName", "")
                full_address = ", ".join(lines + [city]) if lines else city

                # Extract amenities from room description
                room_desc = primary_offer.get("room", {}).get("description", {}).get("text", "")
                amenities = [room_desc] if room_desc else []
                # (Amadeus usually provides a list of amenities in hotel_info, 
                # but it varies between API versions)
                if "amenities" in hotel_info:
                    amenities.extend(hotel_info["amenities"])

                # Map to HotelOption schema
                option = HotelOption(
                    name=hotel_info.get("name", "Unknown Hotel"),
                    hotel_id=hotel_info.get("hotelId"),
                    address=full_address,
                    city=city,
                    rating=float(hotel_info.get("rating", 0)),
                    price_per_night=price_per_night,
                    total_price=total_price,
                    currency=price_info.get("currency", input_params.currency),
                    amenities=list(set(amenities))[:10], # Keep it concise
                    source_url=None, # Amadeus doesn't always return a direct URL
                )
                
                hotel_options.append(option)
                
                # Stop if we have enough results
                if len(hotel_options) >= input_params.max_results:
                    break
                    
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Failed to parse individual hotel offer: {e}")
                continue

        logger.info(f"Successfully parsed {len(hotel_options)} hotel options")
        return hotel_options

    except Exception as e:
        logger.error(f"Error in search_hotels_tool: {e}", exc_info=True)
        raise e


def _is_in_price_range(price: float, range_type: PriceRange, currency: str) -> bool:
    """
    Simple heuristic to filter hotels by price tier.
    
    Budget: < $100
    Mid: $100 - $300
    Luxury: > $300
    (Rough USD estimates)
    """
    # Simple USD mapping (would need more complex logic for other currencies)
    if range_type == PriceRange.BUDGET:
        return price < 100
    elif range_type == PriceRange.MID:
        return 100 <= price <= 300
    elif range_type == PriceRange.LUXURY:
        return price > 300
    return True
