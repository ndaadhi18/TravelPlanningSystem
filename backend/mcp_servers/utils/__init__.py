"""
MCP Server utilities.

Exports the Amadeus client and error handling utilities.
"""

from backend.mcp_servers.utils.amadeus_client import (
    AmadeusClient,
    get_amadeus_client,
)
from backend.mcp_servers.utils.error_handler import (
    ErrorCode,
    MCPToolError,
    format_amadeus_error,
    format_error_response,
)

__all__ = [
    # Amadeus client
    "AmadeusClient",
    "get_amadeus_client",
    # Error handling
    "ErrorCode",
    "MCPToolError",
    "format_error_response",
    "format_amadeus_error",
]
