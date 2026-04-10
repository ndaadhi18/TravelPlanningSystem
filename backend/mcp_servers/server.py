"""
PLANIT MCP Server entry point.

Initializes the FastMCP server and registers all flight, hotel,
and local insight discovery tools.
"""

from fastmcp import FastMCP

from backend.core.settings import get_settings
from backend.mcp_servers.tools.search_hotels import search_hotels_tool
from backend.schemas.accommodation import HotelSearchInput
from backend.schemas.transport import FlightSearchInput

# Configure logging
logger = get_logger("mcp.server")
settings = get_settings()

# Initialize FastMCP server
mcp = FastMCP(
    "PLANIT_MCP",
    description="MCP server for travel planning tools (flights, hotels, attractions)",
)

# ─── Tool Registration ───────────────────────────────────────────────

@mcp.tool()
async def search_flights(params: FlightSearchInput):
    """
    Search for flight offers based on origin, destination, and dates.
    
    Args:
        params: Flight search parameters including origin, destination, and departure_date.
    """
    return await search_flights_tool(params)


@mcp.tool()
async def search_hotels(params: HotelSearchInput):
    """
    Search for hotel accommodations based on city, dates, and preferences.
    
    Args:
        params: Hotel search parameters including city_code, check_in, and check_out.
    """
    return await search_hotels_tool(params)

# @mcp.tool()
# async def web_search_places(params: WebSearchInput):
#     return await web_search_places_tool(params)


# ─── Main ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting PLANIT MCP Server in {settings.app_env} mode")
    mcp.run()
