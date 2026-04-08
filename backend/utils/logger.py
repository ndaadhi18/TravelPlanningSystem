"""
Structured logging setup for PLANIT.

Provides module-specific loggers with:
- Human-readable format in development
- JSON format in production (for log aggregation)
- Log level controlled via Settings
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone

# Cache for created loggers
_loggers: dict[str, logging.Logger] = {}

# Root logger name for the application
ROOT_LOGGER_NAME = "planit"

# Pattern to detect potential secrets in log context
_SECRET_PATTERNS = re.compile(
    r"(api[_-]?key|secret|password|token|credential|auth)",
    re.IGNORECASE,
)


class JSONFormatter(logging.Formatter):
    """JSON formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if any
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        return json.dumps(log_entry)


class DevFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Shorten logger name for readability
        logger_name = record.name.replace(f"{ROOT_LOGGER_NAME}.", "")

        base = f"{timestamp} | {color}{record.levelname:<8}{reset} | {logger_name} | {record.getMessage()}"

        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


def _get_log_level() -> int:
    """Get log level from settings, with fallback."""
    try:
        from backend.core.settings import get_settings
        level_str = get_settings().log_level
    except Exception:
        level_str = "DEBUG"

    return getattr(logging, level_str.upper(), logging.DEBUG)


def _is_production() -> bool:
    """Check if running in production mode."""
    try:
        from backend.core.settings import get_settings
        return get_settings().is_production
    except Exception:
        return False


def _setup_root_logger() -> logging.Logger:
    """Configure the root application logger."""
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(_get_log_level())

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(_get_log_level())

    # Choose formatter based on environment
    if _is_production():
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevFormatter())

    logger.addHandler(handler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a module-specific logger.

    Args:
        name: Logger name (e.g., "agents.greeting", "mcp.flights").
              Will be prefixed with "planit." automatically.

    Returns:
        Configured logger instance.

    Example:
        logger = get_logger("agents.greeting")
        logger.info("Processing user message")
    """
    full_name = f"{ROOT_LOGGER_NAME}.{name}" if name else ROOT_LOGGER_NAME

    if full_name in _loggers:
        return _loggers[full_name]

    # Ensure root logger is configured
    _setup_root_logger()

    # Create child logger
    logger = logging.getLogger(full_name)
    _loggers[full_name] = logger

    return logger


def reset_loggers() -> None:
    """
    Reset all cached loggers.
    
    Useful for test isolation to ensure clean logger state between tests.
    """
    global _loggers
    
    # Clear handlers from root logger
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.handlers.clear()
    
    # Clear the cache
    _loggers = {}


def _sanitize_context(context: dict) -> dict:
    """Redact potential secrets from log context."""
    sanitized = {}
    for key, value in context.items():
        if _SECRET_PATTERNS.search(key):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    return sanitized


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context,
) -> None:
    """
    Log a message with additional context data.

    In production (JSON mode), context appears in the 'extra' field.
    In development, context is appended to the message.
    
    Automatically redacts values for keys containing 'secret', 'key', 
    'password', 'token', or 'credential'.

    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        message: Log message
        **context: Additional key-value context
    """
    if context:
        # Sanitize context to redact potential secrets
        safe_context = _sanitize_context(context)
        
        if _is_production():
            # Add as structured data
            extra = {"extra_data": safe_context}
            logger.log(level, message, extra=extra)
        else:
            # Append to message
            ctx_str = " | ".join(f"{k}={v}" for k, v in safe_context.items())
            logger.log(level, f"{message} | {ctx_str}")
    else:
        logger.log(level, message)
