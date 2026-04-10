"""
PLANIT MCP server entry point.

Assembles a single FastMCP process and registers all travel tools.
"""

from __future__ import annotations

import inspect
import os
from typing import Any

from fastmcp import FastMCP

from backend.core.settings import get_settings
from backend.mcp_servers.tools.search_flights import search_flights_tool
from backend.mcp_servers.tools.search_hotels import search_hotels_tool
from backend.mcp_servers.tools.web_search_places import web_search_places_tool
from backend.schemas.accommodation import HotelSearchInput
from backend.schemas.itinerary import WebSearchInput
from backend.schemas.transport import FlightSearchInput
from backend.utils.logger import get_logger

logger = get_logger("mcp.server")
settings = get_settings()

# Single MCP server process as defined in IMPLEMENTATION.md
mcp = FastMCP(
    "planit_mcp"
)


@mcp.tool()
async def search_flights(params: FlightSearchInput):
    """MCP tool wrapper for flight search."""
    return await search_flights_tool(params)


@mcp.tool()
async def search_hotels(params: HotelSearchInput):
    """MCP tool wrapper for hotel search."""
    return await search_hotels_tool(params)


@mcp.tool()
async def web_search_places(params: WebSearchInput):
    """MCP tool wrapper for local place search."""
    return await web_search_places_tool(params)


def _build_streamable_http_kwargs() -> dict[str, Any]:
    """
    Build kwargs for streamable HTTP mode based on FastMCP runtime signature.

    This keeps startup resilient across FastMCP versions that expose different
    `run()` parameters.
    """
    signature = inspect.signature(mcp.run)
    kwargs: dict[str, Any] = {}

    if "transport" not in signature.parameters:
        raise RuntimeError("Installed FastMCP version does not support transport selection.")

    kwargs["transport"] = "streamable-http"
    if "host" in signature.parameters:
        kwargs["host"] = settings.mcp_server_host
    if "port" in signature.parameters:
        kwargs["port"] = settings.mcp_server_port
    return kwargs


def run_server(transport: str | None = None) -> None:
    """
    Run MCP server in stdio or streamable HTTP mode.

    Args:
        transport: Optional explicit transport. If not provided, uses
            `MCP_TRANSPORT` env var and defaults to `stdio`.
    """
    selected = (transport or os.getenv("MCP_TRANSPORT", "stdio")).strip().lower()
    logger.info(f"Starting PLANIT MCP Server in {settings.app_env} mode, transport={selected}")

    if selected in {"stdio", ""}:
        mcp.run()
        return

    if selected in {"streamable-http", "streamable_http", "http"}:
        mcp.run(**_build_streamable_http_kwargs())
        return

    raise ValueError(
        f"Unsupported MCP transport '{selected}'. Use 'stdio' or 'streamable-http'."
    )


if __name__ == "__main__":
    run_server()
