"""
Utility helper functions for PLANIT.

Date parsing, currency formatting, text utilities, and common operations
used across agents, MCP tools, and API layers.
"""

import re
from datetime import date, timedelta
from typing import Optional


# ─── Date Functions ─────────────────────────────────────────────────────


def parse_date(value: str) -> date:
    """
    Parse a date string into a date object.

    Handles common formats:
    - ISO: "2025-06-15"
    - US: "06/15/2025", "6/15/2025"
    - EU: "15/06/2025", "15-06-2025"
    - Written: "June 15, 2025", "15 Jun 2025", "Jun 15 2025"
    
    NOTE: For ambiguous numerical formats like "05/06/2025", this function
    defaults to US format (MM/DD/YYYY) unless the first part > 12.

    Args:
        value: Date string to parse

    Returns:
        Parsed date object

    Raises:
        ValueError: If date cannot be parsed
    """
    value = value.strip()

    # Try ISO format first (most common in our schemas)
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    # Month name mappings
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    # Pattern: "June 15, 2025" or "Jun 15 2025"
    match = re.match(
        r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",
        value,
        re.IGNORECASE,
    )
    if match:
        month_str, day_str, year_str = match.groups()
        month = months.get(month_str.lower())
        if month:
            return date(int(year_str), month, int(day_str))

    # Pattern: "15 Jun 2025" or "15 June 2025"
    match = re.match(
        r"(\d{1,2})\s+(\w+)\s+(\d{4})",
        value,
        re.IGNORECASE,
    )
    if match:
        day_str, month_str, year_str = match.groups()
        month = months.get(month_str.lower())
        if month:
            return date(int(year_str), month, int(day_str))

    # Pattern: "06/15/2025" or "6/15/2025" (ambiguous US/EU format)
    # Strategy: If first part > 12, it must be day (EU). Otherwise assume US (MM/DD/YYYY).
    # Note: Dates like 12/11/2025 are ambiguous — we default to US (Dec 11).
    match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if match:
        part1, part2, year_str = match.groups()
        p1, p2 = int(part1), int(part2)
        
        if p1 > 12 and p2 <= 12:
            # First part > 12 means it must be day (EU: DD/MM/YYYY)
            return date(int(year_str), p2, p1)
        elif p1 <= 12 and p2 > 31:
            raise ValueError(f"Invalid date: '{value}' — day value {p2} out of range")
        elif p1 <= 12:
            # Assume US format (MM/DD/YYYY) when ambiguous
            return date(int(year_str), p1, p2)
        else:
            raise ValueError(f"Invalid date: '{value}' — cannot determine format")

    # Pattern: "15-06-2025" or "06-15-2025" (ambiguous with dashes)
    # Same logic as above
    match = re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})", value)
    if match:
        part1, part2, year_str = match.groups()
        p1, p2 = int(part1), int(part2)
        
        if p1 > 12 and p2 <= 12:
            # First part > 12 means it must be day (EU: DD-MM-YYYY)
            return date(int(year_str), p2, p1)
        elif p1 <= 12 and p2 > 31:
            raise ValueError(f"Invalid date: '{value}' — day value {p2} out of range")
        elif p1 <= 12:
            # Assume US format (MM-DD-YYYY) when ambiguous
            return date(int(year_str), p1, p2)
        else:
            raise ValueError(f"Invalid date: '{value}' — cannot determine format")

    raise ValueError(f"Could not parse date: '{value}'")


def format_date(d: date) -> str:
    """
    Format a date to ISO string.

    Args:
        d: Date object

    Returns:
        ISO format string "YYYY-MM-DD"
    """
    return d.isoformat()


def calculate_duration(start: str, end: str) -> int:
    """
    Calculate the number of days between two dates.

    Args:
        start: Start date (ISO format or parseable string)
        end: End date (ISO format or parseable string)

    Returns:
        Number of days (end - start)

    Raises:
        ValueError: If dates cannot be parsed or end < start
    """
    start_date = parse_date(start)
    end_date = parse_date(end)

    delta = (end_date - start_date).days

    if delta < 0:
        raise ValueError(f"End date ({end}) is before start date ({start})")

    return delta


def generate_date_range(start: str, days: int) -> list[str]:
    """
    Generate a list of consecutive ISO date strings.

    Args:
        start: Start date (ISO format or parseable string)
        days: Number of days to generate (must be >= 1)

    Returns:
        List of ISO date strings

    Raises:
        ValueError: If days < 1

    Example:
        generate_date_range("2025-06-15", 3)
        # -> ["2025-06-15", "2025-06-16", "2025-06-17"]
    """
    if days < 1:
        raise ValueError(f"days must be >= 1, got {days}")
    
    start_date = parse_date(start)
    return [
        format_date(start_date + timedelta(days=i))
        for i in range(days)
    ]


def is_valid_date(value: str) -> bool:
    """
    Check if a string is a valid parseable date.

    Args:
        value: Date string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        parse_date(value)
        return True
    except (ValueError, TypeError):
        return False


# ─── Currency Functions ─────────────────────────────────────────────────


# Currency symbols for common currencies
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "INR": "₹",
    "JPY": "¥",
    "CNY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "CHF": "CHF",
    "KRW": "₩",
}


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format a monetary amount with currency symbol and proper formatting.

    Args:
        amount: Numeric amount
        currency: ISO 4217 currency code (default: USD)

    Returns:
        Formatted string like "$3,000.00" or "€2,500.00"
    """
    currency = currency.upper()
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")

    # Format with thousands separator and 2 decimal places
    # Exception: JPY and KRW typically don't use decimals
    if currency in ("JPY", "KRW"):
        formatted = f"{amount:,.0f}"
    else:
        formatted = f"{amount:,.2f}"

    return f"{symbol}{formatted}"


def parse_budget(text: str) -> Optional[float]:
    """
    Parse a budget string into a numeric value.

    Handles formats like:
    - "3000", "3,000", "3000.00"
    - "$3000", "€2500", "3000 USD", "CHF 3000"
    - "3k", "3K" (thousands)
    - "1.5k" (1500)

    Args:
        text: Budget string to parse

    Returns:
        Parsed float value, or None if parsing fails
    """
    if not text:
        return None

    text = text.strip()

    # Remove all characters except digits, decimal point, and k/m suffixes
    # This handles currency symbols, alphabetic codes (USD, EUR), and whitespace/commas
    text = re.sub(r"[^0-9.kmKM]", "", text)

    if not text:
        return None

    # Handle "k" suffix (thousands)
    match = re.match(r"^([\d.]+)[kK]$", text)
    if match:
        try:
            return float(match.group(1)) * 1000
        except ValueError:
            return None

    # Handle "m" suffix (millions)
    match = re.match(r"^([\d.]+)[mM]$", text)
    if match:
        try:
            return float(match.group(1)) * 1_000_000
        except ValueError:
            return None

    # Try direct float conversion
    try:
        return float(text)
    except ValueError:
        return None


# ─── Text Functions ─────────────────────────────────────────────────────


def truncate_text(text: str, max_len: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with an ellipsis.

    Args:
        text: Text to truncate
        max_len: Maximum length (including suffix)
        suffix: Suffix to add when truncating (default: "...")

    Returns:
        Truncated string
    """
    if len(text) <= max_len:
        return text

    # Account for suffix length
    truncate_at = max_len - len(suffix)
    if truncate_at <= 0:
        return suffix[:max_len]

    return text[:truncate_at].rstrip() + suffix


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase slug with hyphens
    """
    # Lowercase and replace spaces/underscores with hyphens
    slug = text.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Remove consecutive hyphens
    slug = re.sub(r"-+", "-", slug)

    # Strip leading/trailing hyphens
    return slug.strip("-")


def sanitize_for_display(text: str, max_len: int = 100) -> str:
    """
    Sanitize text for safe display (logs, UI).

    Removes control characters, normalizes whitespace, and truncates.

    Args:
        text: Raw text
        max_len: Maximum length

    Returns:
        Sanitized text
    """
    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    # Normalize whitespace
    text = " ".join(text.split())

    return truncate_text(text, max_len)
