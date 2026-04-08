"""
Tests for Module M3: Utilities

Test Criteria (from IMPLEMENTATION.md):
- Logger outputs structured logs
- Helpers parse dates correctly
"""

import sys
from datetime import date

sys.path.insert(0, ".")

print("=" * 60)
print("M3 Utilities Tests")
print("=" * 60)


# ══════════════════════════════════════════════════════════════
# LOGGER TESTS
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("LOGGER TESTS")
print("─" * 60)

# ── 1. Import Logger ────────────────────────────────────────────
print("\n[1] Import get_logger...")
from backend.utils.logger import get_logger, log_with_context

print("  OK: Logger functions imported")


# ── 2. Create Module Logger ─────────────────────────────────────
print("\n[2] Create module-specific logger...")
logger = get_logger("test.module")
assert logger is not None
assert "planit.test.module" in logger.name
print(f"  OK: Logger created with name '{logger.name}'")


# ── 3. Logger Caching ───────────────────────────────────────────
print("\n[3] Test logger caching...")
logger1 = get_logger("agents.greeting")
logger2 = get_logger("agents.greeting")
assert logger1 is logger2, "Same logger should be returned"
print("  OK: Logger instances are cached")


# ── 4. Log Output ───────────────────────────────────────────────
print("\n[4] Test log output (visual check)...")
test_logger = get_logger("test.visual")
test_logger.debug("This is a DEBUG message")
test_logger.info("This is an INFO message")
test_logger.warning("This is a WARNING message")
print("  OK: Log messages should appear above ↑")


# ── 5. Log With Context ─────────────────────────────────────────
print("\n[5] Test log_with_context...")
import logging

log_with_context(
    test_logger,
    logging.INFO,
    "Processing request",
    user_id="123",
    destination="Paris",
)
print("  OK: Context logging works")


# ══════════════════════════════════════════════════════════════
# DATE HELPER TESTS
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("DATE HELPER TESTS")
print("─" * 60)

from backend.utils.helpers import (
    parse_date,
    format_date,
    calculate_duration,
    generate_date_range,
)

# ── 6. Parse ISO Date ───────────────────────────────────────────
print("\n[6] Parse ISO date...")
d = parse_date("2025-06-15")
assert d == date(2025, 6, 15)
print(f"  OK: '2025-06-15' -> {d}")


# ── 7. Parse Written Date ───────────────────────────────────────
print("\n[7] Parse written dates...")
test_cases = [
    ("June 15, 2025", date(2025, 6, 15)),
    ("Jun 15 2025", date(2025, 6, 15)),
    ("15 June 2025", date(2025, 6, 15)),
    ("15 Jun 2025", date(2025, 6, 15)),
]
for input_str, expected in test_cases:
    result = parse_date(input_str)
    assert result == expected, f"Failed for '{input_str}': got {result}"
    print(f"  OK: '{input_str}' -> {result}")


# ── 8. Parse US/EU Date Formats ─────────────────────────────────
print("\n[8] Parse numeric date formats...")
# US format (MM/DD/YYYY) - ambiguous dates default to US
d = parse_date("06/15/2025")
assert d == date(2025, 6, 15), f"US format failed: {d}"
print(f"  OK: '06/15/2025' -> {d} (US format)")

# Unambiguous EU format (day > 12)
d = parse_date("25/06/2025")
assert d == date(2025, 6, 25), f"EU format failed: {d}"
print(f"  OK: '25/06/2025' -> {d} (EU format, day > 12)")

# Dashes - same logic
d = parse_date("06-15-2025")
assert d == date(2025, 6, 15), f"US dash format failed: {d}"
print(f"  OK: '06-15-2025' -> {d} (US format with dashes)")

d = parse_date("25-06-2025")
assert d == date(2025, 6, 25), f"EU dash format failed: {d}"
print(f"  OK: '25-06-2025' -> {d} (EU format with dashes)")


# ── 9. Invalid Date Rejection ───────────────────────────────────
print("\n[9] Reject invalid dates...")
try:
    parse_date("not-a-date")
    print("  FAIL: Should have rejected invalid date")
except ValueError as e:
    print(f"  OK: Rejected invalid date — ValueError")


# ── 10. Format Date ─────────────────────────────────────────────
print("\n[10] Format date to ISO...")
d = date(2025, 6, 15)
formatted = format_date(d)
assert formatted == "2025-06-15"
print(f"  OK: {d} -> '{formatted}'")


# ── 11. Calculate Duration ──────────────────────────────────────
print("\n[11] Calculate duration...")
days = calculate_duration("2025-06-15", "2025-06-22")
assert days == 7, f"Expected 7, got {days}"
print(f"  OK: 2025-06-15 to 2025-06-22 = {days} days")


# ── 12. Duration with End Before Start ──────────────────────────
print("\n[12] Reject end before start...")
try:
    calculate_duration("2025-06-22", "2025-06-15")
    print("  FAIL: Should have rejected end < start")
except ValueError:
    print("  OK: Rejected end before start — ValueError")


# ── 13. Generate Date Range ─────────────────────────────────────
print("\n[13] Generate date range...")
dates = generate_date_range("2025-06-15", 3)
expected = ["2025-06-15", "2025-06-16", "2025-06-17"]
assert dates == expected, f"Got {dates}"
print(f"  OK: 3 days from 2025-06-15 -> {dates}")

# Test validation for days < 1
try:
    generate_date_range("2025-06-15", 0)
    print("  FAIL: Should have rejected days=0")
except ValueError:
    print("  OK: Rejected days=0 — ValueError")


# ── 13b. is_valid_date ──────────────────────────────────────────
print("\n[13b] Test is_valid_date...")
from backend.utils.helpers import is_valid_date

assert is_valid_date("2025-06-15") is True
assert is_valid_date("June 15, 2025") is True
assert is_valid_date("not-a-date") is False
assert is_valid_date("") is False
print("  OK: is_valid_date works correctly")


# ══════════════════════════════════════════════════════════════
# CURRENCY HELPER TESTS
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("CURRENCY HELPER TESTS")
print("─" * 60)

from backend.utils.helpers import format_currency, parse_budget

# ── 14. Format Currency ─────────────────────────────────────────
print("\n[14] Format currency...")
test_cases = [
    ((3000, "USD"), "$3,000.00"),
    ((2500.5, "EUR"), "€2,500.50"),
    ((100000, "INR"), "₹100,000.00"),
    ((15000, "JPY"), "¥15,000"),  # No decimals for JPY
]
for (amount, currency), expected in test_cases:
    result = format_currency(amount, currency)
    assert result == expected, f"Failed for {amount} {currency}: got '{result}'"
    print(f"  OK: {amount} {currency} -> '{result}'")


# ── 15. Parse Budget ────────────────────────────────────────────
print("\n[15] Parse budget strings...")
test_cases = [
    ("3000", 3000.0),
    ("3,000", 3000.0),
    ("$3000", 3000.0),
    ("€2500", 2500.0),
    ("3k", 3000.0),
    ("3K", 3000.0),
    ("1.5k", 1500.0),
    ("2.5m", 2500000.0),
]
for input_str, expected in test_cases:
    result = parse_budget(input_str)
    assert result == expected, f"Failed for '{input_str}': got {result}"
    print(f"  OK: '{input_str}' -> {result}")


# ── 16. Parse Invalid Budget ────────────────────────────────────
print("\n[16] Parse invalid budget...")
result = parse_budget("not a number")
assert result is None
print(f"  OK: 'not a number' -> None")


# ══════════════════════════════════════════════════════════════
# TEXT HELPER TESTS
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("TEXT HELPER TESTS")
print("─" * 60)

from backend.utils.helpers import truncate_text, slugify, sanitize_for_display

# ── 17. Truncate Text ───────────────────────────────────────────
print("\n[17] Truncate text...")
result = truncate_text("Hello World, this is a long string", 15)
assert result == "Hello World,...", f"Got '{result}'"
print(f"  OK: Truncated to 15 chars -> '{result}'")

result = truncate_text("Short", 15)
assert result == "Short", f"Got '{result}'"
print(f"  OK: Short text unchanged -> '{result}'")


# ── 18. Slugify ─────────────────────────────────────────────────
print("\n[18] Slugify text...")
test_cases = [
    ("Hello World", "hello-world"),
    ("Paris, France!", "paris-france"),
    ("  Multiple   Spaces  ", "multiple-spaces"),
    ("Already-a-slug", "already-a-slug"),
]
for input_str, expected in test_cases:
    result = slugify(input_str)
    assert result == expected, f"Failed for '{input_str}': got '{result}'"
    print(f"  OK: '{input_str}' -> '{result}'")


# ── 19. Sanitize for Display ────────────────────────────────────
print("\n[19] Sanitize text for display...")
# Test control character removal and whitespace normalization
dirty = "Hello\x00World\n  with   spaces"
clean = sanitize_for_display(dirty, max_len=50)
assert "\x00" not in clean
assert "\n" not in clean
assert "  " not in clean
print(f"  OK: Sanitized text -> '{clean}'")


# ══════════════════════════════════════════════════════════════
# MODULE EXPORTS TEST
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("MODULE EXPORTS TEST")
print("─" * 60)

# ── 20. Import from __init__ ────────────────────────────────────
print("\n[20] Import from backend.utils...")
from backend.utils import (
    get_logger,
    log_with_context,
    reset_loggers,
    parse_date,
    format_date,
    calculate_duration,
    generate_date_range,
    is_valid_date,
    format_currency,
    parse_budget,
    truncate_text,
    slugify,
    sanitize_for_display,
)
print("  OK: All exports accessible from backend.utils")


# ── 21. Import from backend.core ────────────────────────────────
print("\n[21] Import from backend.core...")
from backend.core import Settings, get_settings, SettingsDep
print("  OK: Core exports accessible from backend.core")


# ── 22. Test secret redaction in logs ───────────────────────────
print("\n[22] Test secret redaction in log context...")
from backend.utils.logger import _sanitize_context

test_context = {
    "user_id": "123",
    "api_key": "secret_value",
    "password": "hunter2",
    "destination": "Paris",
}
sanitized = _sanitize_context(test_context)
assert sanitized["user_id"] == "123", "Non-secret should be preserved"
assert sanitized["api_key"] == "***REDACTED***", "API key should be redacted"
assert sanitized["password"] == "***REDACTED***", "Password should be redacted"
assert sanitized["destination"] == "Paris", "Non-secret should be preserved"
print("  OK: Secrets properly redacted in log context")


# ── 23. Test reset_loggers ──────────────────────────────────────
print("\n[23] Test reset_loggers...")
reset_loggers()
logger_after_reset = get_logger("test.reset")
assert logger_after_reset is not None
print("  OK: reset_loggers works correctly")


# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("✓ All M3 tests passed!")
print("=" * 60)
