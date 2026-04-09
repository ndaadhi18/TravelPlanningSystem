"""
Amadeus API client wrapper for PLANIT MCP tools.

Provides a unified interface for flight and hotel searches,
with support for mock mode when API credentials are not configured.
"""

from functools import lru_cache
from typing import Any, Optional

from backend.core.settings import get_settings
from backend.mcp_servers.utils.error_handler import (
    ErrorCode,
    MCPToolError,
    format_amadeus_error,
)
from backend.utils.logger import get_logger

logger = get_logger("mcp.amadeus")


# ─── Mock Data ──────────────────────────────────────────────────────────

MOCK_FLIGHT_RESPONSE = {
    "data": [
        {
            "type": "flight-offer",
            "id": "1",
            "source": "GDS",
            "instantTicketingRequired": False,
            "nonHomogeneous": False,
            "oneWay": False,
            "lastTicketingDate": "2025-06-10",
            "numberOfBookableSeats": 9,
            "itineraries": [
                {
                    "duration": "PT8H30M",
                    "segments": [
                        {
                            "departure": {
                                "iataCode": "BOM",
                                "terminal": "2",
                                "at": "2025-06-15T02:15:00",
                            },
                            "arrival": {
                                "iataCode": "CDG",
                                "terminal": "2E",
                                "at": "2025-06-15T08:45:00",
                            },
                            "carrierCode": "AF",
                            "number": "218",
                            "aircraft": {"code": "77W"},
                            "operating": {"carrierCode": "AF"},
                            "duration": "PT8H30M",
                            "id": "1",
                            "numberOfStops": 0,
                            "blacklistedInEU": False,
                        }
                    ],
                }
            ],
            "price": {
                "currency": "USD",
                "total": "856.00",
                "base": "720.00",
                "fees": [{"amount": "0.00", "type": "SUPPLIER"}],
                "grandTotal": "856.00",
            },
            "pricingOptions": {"fareType": ["PUBLISHED"], "includedCheckedBagsOnly": True},
            "validatingAirlineCodes": ["AF"],
            "travelerPricings": [
                {
                    "travelerId": "1",
                    "fareOption": "STANDARD",
                    "travelerType": "ADULT",
                    "price": {"currency": "USD", "total": "856.00", "base": "720.00"},
                    "fareDetailsBySegment": [
                        {
                            "segmentId": "1",
                            "cabin": "ECONOMY",
                            "fareBasis": "EOBFR",
                            "class": "E",
                            "includedCheckedBags": {"weight": 23, "weightUnit": "KG"},
                        }
                    ],
                }
            ],
        },
        {
            "type": "flight-offer",
            "id": "2",
            "source": "GDS",
            "itineraries": [
                {
                    "duration": "PT10H45M",
                    "segments": [
                        {
                            "departure": {
                                "iataCode": "BOM",
                                "terminal": "2",
                                "at": "2025-06-15T14:30:00",
                            },
                            "arrival": {
                                "iataCode": "CDG",
                                "terminal": "1",
                                "at": "2025-06-15T23:15:00",
                            },
                            "carrierCode": "LH",
                            "number": "765",
                            "duration": "PT10H45M",
                            "id": "2",
                            "numberOfStops": 1,
                        }
                    ],
                }
            ],
            "price": {
                "currency": "USD",
                "total": "692.00",
                "grandTotal": "692.00",
            },
            "validatingAirlineCodes": ["LH"],
        },
    ],
    "dictionaries": {
        "carriers": {"AF": "AIR FRANCE", "LH": "LUFTHANSA"},
        "aircraft": {"77W": "BOEING 777-300ER"},
    },
}

MOCK_HOTELS_BY_CITY_RESPONSE = {
    "data": [
        {
            "type": "hotel",
            "hotelId": "HLPAR123",
            "name": "Hotel Le Marais",
            "iataCode": "PAR",
            "address": {
                "countryCode": "FR",
                "cityName": "Paris",
                "lines": ["15 Rue du Temple"],
            },
            "geoCode": {"latitude": 48.8566, "longitude": 2.3522},
        },
        {
            "type": "hotel",
            "hotelId": "HLPAR456",
            "name": "Grand Hotel Opera",
            "iataCode": "PAR",
            "address": {
                "countryCode": "FR",
                "cityName": "Paris",
                "lines": ["2 Rue Scribe"],
            },
            "geoCode": {"latitude": 48.8708, "longitude": 2.3318},
        },
        {
            "type": "hotel",
            "hotelId": "HLPAR789",
            "name": "Budget Inn Montmartre",
            "iataCode": "PAR",
            "address": {
                "countryCode": "FR",
                "cityName": "Paris",
                "lines": ["45 Rue Lepic"],
            },
            "geoCode": {"latitude": 48.8845, "longitude": 2.3388},
        },
    ]
}

MOCK_HOTEL_OFFERS_RESPONSE = {
    "data": [
        {
            "type": "hotel-offers",
            "hotel": {
                "type": "hotel",
                "hotelId": "HLPAR123",
                "name": "Hotel Le Marais",
                "rating": "4",
                "cityCode": "PAR",
                "address": {
                    "lines": ["15 Rue du Temple"],
                    "cityName": "Paris",
                    "countryCode": "FR",
                },
            },
            "available": True,
            "offers": [
                {
                    "id": "OFFER1",
                    "checkInDate": "2025-06-15",
                    "checkOutDate": "2025-06-22",
                    "rateCode": "BAR",
                    "room": {
                        "type": "DOUBLE",
                        "typeEstimated": {"category": "STANDARD_ROOM", "beds": 1, "bedType": "DOUBLE"},
                        "description": {"text": "Standard Double Room with City View"},
                    },
                    "guests": {"adults": 2},
                    "price": {
                        "currency": "USD",
                        "base": "980.00",
                        "total": "1120.00",
                        "variations": {
                            "average": {"base": "140.00"},
                            "changes": [{"startDate": "2025-06-15", "endDate": "2025-06-22", "base": "140.00"}],
                        },
                    },
                }
            ],
        },
        {
            "type": "hotel-offers",
            "hotel": {
                "type": "hotel",
                "hotelId": "HLPAR789",
                "name": "Budget Inn Montmartre",
                "rating": "2",
                "cityCode": "PAR",
            },
            "available": True,
            "offers": [
                {
                    "id": "OFFER2",
                    "checkInDate": "2025-06-15",
                    "checkOutDate": "2025-06-22",
                    "price": {
                        "currency": "USD",
                        "total": "560.00",
                        "variations": {"average": {"base": "80.00"}},
                    },
                }
            ],
        },
    ]
}


# ─── Amadeus Client ─────────────────────────────────────────────────────


class AmadeusClient:
    """
    Wrapper for Amadeus API interactions.

    Supports mock mode when API credentials are not configured,
    allowing development and testing without real API access.
    """

    def __init__(self):
        self._client = None
        self._settings = get_settings()
        self._mock_mode = not self._settings.amadeus_configured

        if self._mock_mode:
            logger.warning(
                "Amadeus credentials not configured. Running in MOCK MODE. "
                "Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET in .env for real API access."
            )
        else:
            logger.info("Amadeus client initialized with real credentials.")

    @property
    def is_mock_mode(self) -> bool:
        """Check if client is running in mock mode."""
        return self._mock_mode

    @property
    def is_configured(self) -> bool:
        """Check if Amadeus credentials are configured."""
        return self._settings.amadeus_configured

    def _get_client(self):
        """Get or create the Amadeus SDK client."""
        if self._mock_mode:
            raise MCPToolError(
                message="Amadeus API not configured. Running in mock mode.",
                code=ErrorCode.NOT_CONFIGURED,
            )

        if self._client is None:
            try:
                from amadeus import Client, ResponseError

                self._client = Client(
                    client_id=self._settings.amadeus_client_id,
                    client_secret=self._settings.amadeus_client_secret,
                    hostname=self._settings.amadeus_hostname,
                )
                logger.info(f"Amadeus client connected to {self._settings.amadeus_hostname} environment")
            except Exception as e:
                logger.error(f"Failed to initialize Amadeus client: {e}")
                raise MCPToolError(
                    message="Failed to initialize Amadeus client",
                    code=ErrorCode.AUTHENTICATION_FAILED,
                    original_error=e,
                )

        return self._client

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        return_date: Optional[str] = None,
        max_results: int = 5,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """
        Search for flight offers.

        Args:
            origin: Origin airport IATA code (e.g., 'BOM')
            destination: Destination airport IATA code (e.g., 'CDG')
            departure_date: Departure date in ISO format (YYYY-MM-DD)
            adults: Number of adult passengers
            return_date: Return date for round-trip (optional)
            max_results: Maximum number of results to return
            currency: Currency code for prices

        Returns:
            Raw Amadeus API response as dictionary

        Raises:
            MCPToolError: On API errors
        """
        logger.info(
            f"Searching flights: {origin} -> {destination} on {departure_date}, "
            f"adults={adults}, max_results={max_results}"
        )

        if self._mock_mode:
            logger.info("Returning mock flight data")
            return MOCK_FLIGHT_RESPONSE

        try:
            from amadeus import ResponseError

            client = self._get_client()

            params = {
                "originLocationCode": origin.upper(),
                "destinationLocationCode": destination.upper(),
                "departureDate": departure_date,
                "adults": adults,
                "currencyCode": currency.upper(),
                "max": max_results,
            }

            if return_date:
                params["returnDate"] = return_date

            response = client.shopping.flight_offers_search.get(**params)
            logger.info(f"Found {len(response.data)} flight offers")
            return response.result

        except Exception as e:
            logger.error(f"Flight search failed: {e}")
            if "ResponseError" in type(e).__name__:
                raise MCPToolError(
                    message=str(e),
                    code=ErrorCode.API_ERROR,
                    details=format_amadeus_error(e),
                    original_error=e,
                )
            raise MCPToolError(
                message=f"Flight search failed: {str(e)}",
                code=ErrorCode.API_ERROR,
                original_error=e,
            )

    def search_hotels_by_city(
        self,
        city_code: str,
        radius: int = 5,
        radius_unit: str = "KM",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """
        Search for hotels in a city.

        Args:
            city_code: IATA city code (e.g., 'PAR' for Paris)
            radius: Search radius from city center
            radius_unit: Unit for radius ('KM' or 'MILE')
            max_results: Maximum number of hotels to return

        Returns:
            Raw Amadeus API response as dictionary

        Raises:
            MCPToolError: On API errors
        """
        logger.info(f"Searching hotels in city: {city_code}, max_results={max_results}")

        if self._mock_mode:
            logger.info("Returning mock hotel list data")
            return MOCK_HOTELS_BY_CITY_RESPONSE

        try:
            client = self._get_client()

            response = client.reference_data.locations.hotels.by_city.get(
                cityCode=city_code.upper(),
                radius=radius,
                radiusUnit=radius_unit,
            )

            # Limit results
            data = response.result
            if "data" in data and len(data["data"]) > max_results:
                data["data"] = data["data"][:max_results]

            logger.info(f"Found {len(data.get('data', []))} hotels")
            return data

        except Exception as e:
            logger.error(f"Hotel search by city failed: {e}")
            raise MCPToolError(
                message=f"Hotel search failed: {str(e)}",
                code=ErrorCode.API_ERROR,
                original_error=e,
            )

    def search_hotel_offers(
        self,
        hotel_ids: list[str],
        check_in: str,
        check_out: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """
        Search for hotel offers/prices.

        Args:
            hotel_ids: List of hotel IDs from search_hotels_by_city
            check_in: Check-in date in ISO format (YYYY-MM-DD)
            check_out: Check-out date in ISO format (YYYY-MM-DD)
            adults: Number of adult guests
            currency: Currency code for prices

        Returns:
            Raw Amadeus API response as dictionary

        Raises:
            MCPToolError: On API errors
        """
        logger.info(
            f"Searching hotel offers: {len(hotel_ids)} hotels, "
            f"{check_in} to {check_out}, adults={adults}"
        )

        if self._mock_mode:
            logger.info("Returning mock hotel offers data")
            return MOCK_HOTEL_OFFERS_RESPONSE

        try:
            client = self._get_client()

            response = client.shopping.hotel_offers_search.get(
                hotelIds=hotel_ids,
                checkInDate=check_in,
                checkOutDate=check_out,
                adults=adults,
                currency=currency.upper(),
            )

            logger.info(f"Found offers for {len(response.data)} hotels")
            return response.result

        except Exception as e:
            logger.error(f"Hotel offers search failed: {e}")
            raise MCPToolError(
                message=f"Hotel offers search failed: {str(e)}",
                code=ErrorCode.API_ERROR,
                original_error=e,
            )


# ─── Singleton Accessor ─────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_amadeus_client() -> AmadeusClient:
    """
    Get the singleton AmadeusClient instance.

    Returns:
        Cached AmadeusClient instance
    """
    return AmadeusClient()
