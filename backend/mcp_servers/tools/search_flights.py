"""
Flight search tool for PLANIT MCP server.

Uses the AmadeusClient to fetch flight offers and maps them to the
standardized FlightOption schema.
"""

from typing import Any

from backend.mcp_servers.utils.amadeus_client import get_amadeus_client
from backend.schemas.transport import FlightOption, FlightSearchInput
from backend.utils.logger import get_logger

logger = get_logger("mcp.tools.search_flights")


async def search_flights_tool(input_params: FlightSearchInput) -> list[FlightOption]:
    """
    Search for flight offers using the Amadeus API.
    
    Args:
        input_params: Structured flight search parameters.
        
    Returns:
        A list of standardized FlightOption objects.
    """
    logger.info(
        f"MCP Tool 'search_flights' called: {input_params.origin} -> "
        f"{input_params.destination} on {input_params.departure_date}"
    )

    try:
        client = get_amadeus_client()
        
        # Call the AmadeusClient wrapper
        raw_response = client.search_flights(
            origin=input_params.origin,
            destination=input_params.destination,
            departure_date=input_params.departure_date,
            adults=input_params.adults,
            return_date=input_params.return_date,
            max_results=input_params.max_results,
            currency=input_params.currency,
        )

        data = raw_response.get("data", [])
        dictionaries = raw_response.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})

        flight_options = []

        for offer in data:
            try:
                # Extract primary itinerary (we focus on the first itinerary for simplicity)
                itinerary = offer.get("itineraries", [{}])[0]
                segments = itinerary.get("segments", [])
                
                if not segments:
                    continue

                first_segment = segments[0]
                last_segment = segments[-1]

                # Extract airline name from dictionary or use carrier code
                carrier_code = first_segment.get("carrierCode", "")
                airline_name = carriers.get(carrier_code, carrier_code)

                # Extract flight number
                flight_number = f"{carrier_code} {first_segment.get('number', '')}"

                # Extract price info
                price_info = offer.get("price", {})
                total_price = float(price_info.get("total", 0.0))
                currency = price_info.get("currency", input_params.currency)

                # Extract cabin class from traveler pricings
                traveler_pricings = offer.get("travelerPricings", [{}])
                fare_details = traveler_pricings[0].get("fareDetailsBySegment", [{}])
                cabin_class = fare_details[0].get("cabin")

                # Calculate total stops: connections between segments + technical stops within segments
                total_stops = len(segments) - 1
                for segment in segments:
                    total_stops += segment.get("numberOfStops", 0)

                # Map to FlightOption schema
                option = FlightOption(
                    airline=airline_name,
                    flight_number=flight_number,
                    origin=first_segment.get("departure", {}).get("iataCode", input_params.origin),
                    destination=last_segment.get("arrival", {}).get("iataCode", input_params.destination),
                    departure_time=first_segment.get("departure", {}).get("at", ""),
                    arrival_time=last_segment.get("arrival", {}).get("at", ""),
                    duration=itinerary.get("duration", ""),
                    price=total_price,
                    currency=currency,
                    stops=total_stops,
                    cabin_class=cabin_class,
                )
                
                flight_options.append(option)
                
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Failed to parse individual flight offer: {e}")
                continue

        logger.info(f"Successfully parsed {len(flight_options)} flight options")
        return flight_options

    except Exception as e:
        logger.error(f"Error in search_flights_tool: {e}", exc_info=True)
        # Re-raise as MCPToolError (handled by AmadeusClient already, 
        # but unexpected errors need wrapping)
        raise e
