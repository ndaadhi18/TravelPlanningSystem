"""
MCP Error handling utilities.

Provides standardized error formatting for MCP tool responses,
ensuring consistent error structure across all tools.
"""

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """Standard error codes for MCP tool responses."""

    # Configuration errors
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INVALID_CONFIG = "INVALID_CONFIG"

    # Authentication errors
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # API errors
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    API_ERROR = "API_ERROR"
    TIMEOUT = "TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Data errors
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MCPToolError(Exception):
    """
    Custom exception for MCP tool errors.

    Provides structured error information that can be serialized
    for MCP responses.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.original_error = original_error

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON serialization."""
        result = {
            "error": True,
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


def format_error_response(
    message: str,
    code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Format a standardized error response for MCP tools.

    Args:
        message: Human-readable error message
        code: Error code from ErrorCode enum
        details: Additional error details

    Returns:
        Dictionary suitable for JSON serialization
    """
    response = {
        "error": True,
        "code": code.value,
        "message": message,
    }
    if details:
        response["details"] = details
    return response


def format_amadeus_error(error: Exception) -> dict[str, Any]:
    """
    Format Amadeus API errors into standardized MCP error responses.

    Args:
        error: Exception from Amadeus SDK

    Returns:
        Formatted error dictionary
    """
    error_str = str(error).lower()

    # Detect specific error types from Amadeus
    if "authentication" in error_str or "unauthorized" in error_str:
        return format_error_response(
            message="Amadeus authentication failed. Check API credentials.",
            code=ErrorCode.AUTHENTICATION_FAILED,
            details={"original_error": str(error)},
        )

    if "rate limit" in error_str or "too many requests" in error_str:
        return format_error_response(
            message="Amadeus API rate limit exceeded. Please wait and retry.",
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details={"original_error": str(error)},
        )

    if "not found" in error_str or "no results" in error_str:
        return format_error_response(
            message="No results found for the given search criteria.",
            code=ErrorCode.NOT_FOUND,
            details={"original_error": str(error)},
        )

    if "timeout" in error_str:
        return format_error_response(
            message="Amadeus API request timed out.",
            code=ErrorCode.TIMEOUT,
            details={"original_error": str(error)},
        )

    # Generic API error
    return format_error_response(
        message=f"Amadeus API error: {str(error)}",
        code=ErrorCode.API_ERROR,
        details={"original_error": str(error)},
    )
