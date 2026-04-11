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
    params = signature.parameters
    kwargs: dict[str, Any] = {}

    supports_var_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in params.values()
    )
    if "transport" not in params and not supports_var_kwargs:
        raise RuntimeError("Installed FastMCP version does not support transport selection.")

    def _accepts(name: str) -> bool:
        return name in params or supports_var_kwargs

    # Keep legacy alias for compatibility with existing tests; fall back to
    # transport="http" at runtime when needed.
    kwargs["transport"] = "streamable-http"
    if _accepts("host"):
        kwargs["host"] = settings.mcp_server_host
    elif _accepts("server_host"):
        kwargs["server_host"] = settings.mcp_server_host

    if _accepts("port"):
        kwargs["port"] = settings.mcp_server_port
    elif _accepts("server_port"):
        kwargs["server_port"] = settings.mcp_server_port

    return kwargs


def run_server(transport: str | None = None) -> None:
    """
    Run MCP server in stdio or streamable HTTP mode.

    Args:
        transport: Optional explicit transport. If not provided, uses
            `MCP_TRANSPORT` env var and defaults to `streamable-http`.
    """
    selected = (transport or os.getenv("MCP_TRANSPORT", "streamable-http")).strip().lower()
    logger.info(f"Starting PLANIT MCP Server in {settings.app_env} mode, transport={selected}")

    if selected in {"stdio", ""}:
        mcp.run()
        return

    if selected in {"streamable-http", "streamable_http", "http"}:
        kwargs = _build_streamable_http_kwargs()
        try:
            mcp.run(**kwargs)
        except (TypeError, ValueError):
            # Newer FastMCP uses transport="http" for streamable HTTP mode.
            kwargs["transport"] = "http"
            mcp.run(**kwargs)
        return

    raise ValueError(
        f"Unsupported MCP transport '{selected}'. Use 'stdio' or 'streamable-http'."
    )


if __name__ == "__main__":
    run_server()
