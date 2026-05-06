"""
AeroDataBox API client for flight schedule data and airport search.

Base URL : https://prod.api.market/api/v1/aedbx/aerodatabox
Auth     : x-api-market-key header (set AERODATABOX_API_KEY in .env)
"""

import asyncio
from functools import lru_cache
from typing import Any

import httpx

from backend.core.settings import get_settings
from backend.mcp_servers.utils.error_handler import ErrorCode, MCPToolError
from backend.utils.logger import get_logger

logger = get_logger("mcp.aerodatabox")

_BASE_URL = "https://prod.api.market/api/v1/aedbx/aerodatabox"


class AeroDataBoxClient:
    """Async HTTP client for the AeroDataBox API via API.market."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = self._settings.aerodatabox_api_key or ""
        self.mock_mode = not self._settings.aerodatabox_configured

        if self.mock_mode:
            logger.warning(
                "AERODATABOX_API_KEY not configured — flight search will use mock data. "
                "Set AERODATABOX_API_KEY in .env for real flight schedules."
            )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-api-market-key": self._api_key,
            "Accept": "application/json",
        }

    # ── Airport Resolution ───────────────────────────────────────────────

    async def search_airports(
        self,
        query: str,
        limit: int = 5,
        with_flight_info_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search airports by city name, airport name, or code.

        Args:
            query: City or airport name (min 3 chars), or IATA/ICAO code.
            limit: Max airports to return (default 5, max 250).
            with_flight_info_only: Only return airports with flight schedule data.

        Returns:
            List of airport dicts. Each item typically contains:
            { "iata": "BOM", "icao": "VABB", "name": "...", "cityName": "Mumbai", ... }
            Returns [] on any error so callers can fall back gracefully.
        """
        if self.mock_mode:
            return []

        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(
                    f"{_BASE_URL}/airports/search/term",
                    headers=self._headers,
                    params={
                        "q": query,
                        "limit": limit,
                        "withFlightInfoOnly": "true" if with_flight_info_only else "false",
                        "withSearchByCode": "true",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                # API may return {"items": [...]} or a bare list
                if isinstance(data, dict):
                    return data.get("items", [])
                return data if isinstance(data, list) else []
            except Exception as e:
                logger.warning(f"Airport search failed for '{query}': {e}")
                return []

    # ── Flight Schedule ──────────────────────────────────────────────────

    async def get_departures(
        self,
        iata_code: str,
        from_local: str,
        to_local: str,
    ) -> list[dict[str, Any]]:
        """
        Get departing flights from an airport within a time window (max 12 h).

        Args:
            iata_code : 3-letter IATA code, e.g. "BOM".
            from_local: Window start — "YYYY-MM-DDTHH:mm".
            to_local  : Window end   — "YYYY-MM-DDTHH:mm" (at most 12 h after start).

        Returns:
            Raw flight dicts from the API's "departures" array.
            Each dict has airline, number, status, departure{}, arrival{} (withLeg=true).

        Raises:
            MCPToolError on HTTP or network errors.
        """
        url = (
            f"{_BASE_URL}/flights/airports/Iata"
            f"/{iata_code.upper()}/{from_local}/{to_local}"
        )
        logger.debug(f"AeroDataBox GET {url}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    url,
                    headers=self._headers,
                    params={
                        "direction": "Departure",
                        "withLeg": "true",       # get arrival airport + time
                        "withCancelled": "false",
                        "withCodeshared": "true",
                        "withCargo": "false",
                        "withPrivate": "false",
                        "withLocation": "false",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("departures", [])

            except httpx.HTTPStatusError as e:
                snippet = e.response.text[:300]
                logger.error(
                    f"AeroDataBox HTTP {e.response.status_code} for "
                    f"{iata_code} {from_local}→{to_local}: {snippet}"
                )
                raise MCPToolError(
                    message=f"AeroDataBox returned HTTP {e.response.status_code}",
                    code=ErrorCode.API_ERROR,
                    details={"status": e.response.status_code, "body": snippet},
                )
            except httpx.TimeoutException:
                raise MCPToolError(
                    message="AeroDataBox request timed out after 15 s",
                    code=ErrorCode.TIMEOUT,
                )
            except MCPToolError:
                raise
            except Exception as e:
                raise MCPToolError(
                    message=f"AeroDataBox request failed: {e}",
                    code=ErrorCode.API_ERROR,
                )

    async def get_full_day_departures(
        self,
        iata_code: str,
        date: str,
    ) -> list[dict[str, Any]]:
        """
        Get all departures for a full calendar day.

        Makes two concurrent 12-hour window calls (00:00–11:59, 12:00–23:59)
        and merges the results.

        Args:
            iata_code: 3-letter IATA code, e.g. "BOM".
            date     : ISO date string "YYYY-MM-DD".

        Returns:
            Combined list of departure flight dicts for the full day.
        """
        windows = [
            (f"{date}T00:00", f"{date}T11:59"),
            (f"{date}T12:00", f"{date}T23:59"),
        ]

        results = await asyncio.gather(
            *[self.get_departures(iata_code, f, t) for f, t in windows],
            return_exceptions=True,
        )

        flights: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Departure window {i + 1} failed: {result}")
            else:
                flights.extend(result)

        logger.info(
            f"AeroDataBox full-day departures for {iata_code} on {date}: "
            f"{len(flights)} flights across both windows"
        )
        return flights


@lru_cache(maxsize=1)
def get_aerodatabox_client() -> AeroDataBoxClient:
    """Singleton AeroDataBox client (created once per process)."""
    return AeroDataBoxClient()
