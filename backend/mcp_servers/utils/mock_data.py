"""
Mock data for MCP tools during development.

Used when real API credentials are not configured or while provider
integrations are being developed. Replace per-tool when the real
provider client is wired in.
"""

# ─── Flight Mock Data ────────────────────────────────────────────────────────
# Realistic Indian domestic and short-haul international routes in INR.

MOCK_FLIGHTS = [
    {
        "airline": "IndiGo",
        "flight_number": "6E 2341",
        "origin": "BOM",
        "destination": "DEL",
        "departure_time": "2025-06-15T06:00:00",
        "arrival_time": "2025-06-15T08:10:00",
        "duration": "PT2H10M",
        "price": 5500.0,
        "currency": "INR",
        "stops": 0,
        "cabin_class": "ECONOMY",
    },
    {
        "airline": "Air India",
        "flight_number": "AI 657",
        "origin": "BOM",
        "destination": "DEL",
        "departure_time": "2025-06-15T09:30:00",
        "arrival_time": "2025-06-15T11:45:00",
        "duration": "PT2H15M",
        "price": 6800.0,
        "currency": "INR",
        "stops": 0,
        "cabin_class": "ECONOMY",
    },
    {
        "airline": "SpiceJet",
        "flight_number": "SG 118",
        "origin": "BOM",
        "destination": "DEL",
        "departure_time": "2025-06-15T13:00:00",
        "arrival_time": "2025-06-15T15:20:00",
        "duration": "PT2H20M",
        "price": 4900.0,
        "currency": "INR",
        "stops": 0,
        "cabin_class": "ECONOMY",
    },
    {
        "airline": "Vistara",
        "flight_number": "UK 945",
        "origin": "BOM",
        "destination": "DEL",
        "departure_time": "2025-06-15T17:30:00",
        "arrival_time": "2025-06-15T19:50:00",
        "duration": "PT2H20M",
        "price": 7200.0,
        "currency": "INR",
        "stops": 0,
        "cabin_class": "ECONOMY",
    },
    {
        "airline": "IndiGo",
        "flight_number": "6E 504",
        "origin": "DEL",
        "destination": "BLR",
        "departure_time": "2025-06-15T07:15:00",
        "arrival_time": "2025-06-15T10:05:00",
        "duration": "PT2H50M",
        "price": 6200.0,
        "currency": "INR",
        "stops": 0,
        "cabin_class": "ECONOMY",
    },
]

# ─── Hotel Mock Data ─────────────────────────────────────────────────────────
# Realistic Indian hotel options in INR per night.

MOCK_HOTELS = [
    {
        "name": "Taj Lands End",
        "hotel_id": "HLMUM001",
        "address": "Bandstand, Bandra West, Mumbai",
        "city": "Mumbai",
        "rating": 4.5,
        "price_per_night": 12000.0,
        "total_price": 36000.0,
        "currency": "INR",
        "amenities": ["Free WiFi", "Pool", "Spa", "Restaurant", "24hr Reception"],
        "source_url": None,
    },
    {
        "name": "The Leela Palace",
        "hotel_id": "HLMUM002",
        "address": "Sahar Airport Road, Andheri, Mumbai",
        "city": "Mumbai",
        "rating": 4.8,
        "price_per_night": 18500.0,
        "total_price": 55500.0,
        "currency": "INR",
        "amenities": ["Spa", "Rooftop Pool", "Concierge", "Fitness Center", "Free WiFi"],
        "source_url": None,
    },
    {
        "name": "Ibis Mumbai Airport",
        "hotel_id": "HLMUM003",
        "address": "Andheri East, Mumbai",
        "city": "Mumbai",
        "rating": 3.5,
        "price_per_night": 4500.0,
        "total_price": 13500.0,
        "currency": "INR",
        "amenities": ["Free WiFi", "24hr Reception", "Restaurant"],
        "source_url": None,
    },
    {
        "name": "Radisson Blu Plaza Delhi",
        "hotel_id": "HLDEL001",
        "address": "National Highway 8, New Delhi",
        "city": "Delhi",
        "rating": 4.2,
        "price_per_night": 8500.0,
        "total_price": 25500.0,
        "currency": "INR",
        "amenities": ["Restaurant", "Bar", "Free WiFi", "Fitness Center", "Pool"],
        "source_url": None,
    },
    {
        "name": "OYO Rooms Connaught Place",
        "hotel_id": "HLDEL002",
        "address": "Connaught Place, New Delhi",
        "city": "Delhi",
        "rating": 3.0,
        "price_per_night": 2200.0,
        "total_price": 6600.0,
        "currency": "INR",
        "amenities": ["Free WiFi", "AC", "24hr Reception"],
        "source_url": None,
    },
]
