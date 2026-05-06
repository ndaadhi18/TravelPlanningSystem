"""
MCP Server utilities.

Exports error handling and mock data utilities for MCP tools.
"""

from backend.mcp_servers.utils.error_handler import (
    ErrorCode,
    MCPToolError,
    format_api_error,
    format_error_response,
)
from backend.mcp_servers.utils.mock_data import MOCK_FLIGHTS, MOCK_HOTELS

__all__ = [
    # Error handling
    "ErrorCode",
    "MCPToolError",
    "format_error_response",
    "format_api_error",
    # Mock data
    "MOCK_FLIGHTS",
    "MOCK_HOTELS",
]
