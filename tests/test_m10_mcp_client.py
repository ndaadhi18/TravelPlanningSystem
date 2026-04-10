"""
Tests for Module M10: MCP Client service.

Validates that MCPClient can:
- instantiate from settings
- call MCP tools with protocol fallback
- parse structured responses into schemas
- surface protocol/shape errors explicitly
- perform basic health checks
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath("."))

from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import LocalInsight
from backend.schemas.transport import FlightOption
from backend.services.mcp_client import MCPClient, MCPClientError


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeHealthClient:
    def __init__(self, status_codes):
        self._status_codes = list(status_codes)
        self._index = 0

    async def get(self, _url: str):
        code = self._status_codes[min(self._index, len(self._status_codes) - 1)]
        self._index += 1
        return _FakeResponse(code)


async def test_m10_mcp_client():
    print("=" * 60)
    print("M10 MCP Client Tests")
    print("=" * 60)

    # ── 1. Instantiation from settings ──────────────────────────────────
    print("\n[1] Testing MCPClient instantiation from settings...")
    fake_settings = SimpleNamespace(mcp_server_url="http://mcp.local:9001")
    with patch("backend.services.mcp_client.get_settings", return_value=fake_settings):
        client = MCPClient()
    assert client.base_url == "http://mcp.local:9001"
    print(f"  OK: base_url resolved from settings -> {client.base_url}")

    # ── 2. Generic tool call fallback behavior ──────────────────────────
    print("\n[2] Testing generic call_tool fallback sequence...")
    client = MCPClient(base_url="http://localhost:8001")
    attempted_urls = []

    async def fake_request(url, _body):
        attempted_urls.append(url)
        if url.endswith("/mcp"):
            raise MCPClientError("mcp endpoint unavailable")
        return {"result": {"data": [{"ok": True}]}}

    client._request_json = fake_request  # type: ignore[attr-defined]
    result = await client.call_tool("search_flights", {"origin": "BOM"})
    assert result == [{"ok": True}]
    assert attempted_urls[0].endswith("/mcp")
    assert attempted_urls[1].endswith("/tools/call")
    print("  OK: call_tool retries alternate request shape after first failure")

    # ── 3. Typed wrappers parse schema outputs ───────────────────────────
    print("\n[3] Testing typed wrapper parsing...")
    client = MCPClient(base_url="http://localhost:8001")

    async def fake_call(tool_name, _payload):
        if tool_name == "search_flights":
            return [
                {
                    "airline": "Air France",
                    "flight_number": "AF 218",
                    "origin": "BOM",
                    "destination": "CDG",
                    "departure_time": "2025-06-15T02:15:00",
                    "arrival_time": "2025-06-15T08:45:00",
                    "duration": "PT8H30M",
                    "price": 856.0,
                    "currency": "USD",
                    "stops": 0,
                }
            ]
        if tool_name == "search_hotels":
            return [
                {
                    "name": "Hotel Le Marais",
                    "hotel_id": "HLPAR123",
                    "address": "15 Rue du Temple, Paris",
                    "city": "Paris",
                    "rating": 4.0,
                    "price_per_night": 140.0,
                    "total_price": 1120.0,
                    "currency": "USD",
                    "amenities": ["WiFi"],
                }
            ]
        return [
            {
                "name": "Le Marais Walk",
                "category": "activity",
                "description": "Explore a classic neighborhood route.",
                "source_url": "https://example.com/marais-walk",
            }
        ]

    client.call_tool = fake_call  # type: ignore[assignment]

    flights = await client.search_flights(
        {
            "origin": "BOM",
            "destination": "CDG",
            "departure_date": "2025-06-15",
        }
    )
    hotels = await client.search_hotels(
        {
            "city_code": "PAR",
            "check_in": "2025-06-15",
            "check_out": "2025-06-22",
        }
    )
    places = await client.web_search_places({"query": "hidden gems in Paris"})

    assert isinstance(flights[0], FlightOption)
    assert isinstance(hotels[0], HotelOption)
    assert isinstance(places[0], LocalInsight)
    print("  OK: typed wrappers return schema-validated model lists")

    # ── 4. MCP error payload handling ────────────────────────────────────
    print("\n[4] Testing MCP error payload handling...")
    client = MCPClient(base_url="http://localhost:8001")

    async def fake_error_response(_url, _body):
        return {"error": {"message": "Tool execution failed", "code": "INTERNAL"}}

    client._request_json = fake_error_response  # type: ignore[attr-defined]
    try:
        await client.call_tool("search_hotels", {"city_code": "PAR"})
        print("  FAIL: Expected MCPClientError for MCP error payload")
        sys.exit(1)
    except MCPClientError as err:
        assert "Tool execution failed" in err.message
        print("  OK: MCP error payload raised MCPClientError")

    # ── 5. Malformed typed response handling ─────────────────────────────
    print("\n[5] Testing malformed typed response handling...")
    client = MCPClient(base_url="http://localhost:8001")

    async def fake_bad_shape(*_args, **_kwargs):
        return {"unexpected": "shape"}

    client.call_tool = fake_bad_shape  # type: ignore[assignment]
    try:
        await client.search_flights(
            {
                "origin": "BOM",
                "destination": "CDG",
                "departure_date": "2025-06-15",
            }
        )
        print("  FAIL: Expected MCPClientError for malformed response shape")
        sys.exit(1)
    except MCPClientError:
        print("  OK: malformed typed response rejected")

    # ── 6. Health check behavior ─────────────────────────────────────────
    print("\n[6] Testing health_check behavior...")
    healthy_client = MCPClient(
        base_url="http://localhost:8001",
        http_client=_FakeHealthClient([503, 200]),  # type: ignore[arg-type]
    )
    unhealthy_client = MCPClient(
        base_url="http://localhost:8001",
        http_client=_FakeHealthClient([503, 503]),  # type: ignore[arg-type]
    )
    assert await healthy_client.health_check() is True
    assert await unhealthy_client.health_check() is False
    print("  OK: health_check returns expected boolean outcomes")

    print("\n" + "=" * 60)
    print("✓ All M10 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_m10_mcp_client())
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
