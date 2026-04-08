"""Tests for critical fixes in Modules M1-M3."""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.schemas.travel_intent import TravelIntent
from backend.utils.helpers import parse_budget, parse_date
from backend.utils.logger import get_logger, log_with_context
import logging
import io

def test_partial_travel_intent():
    print("Testing partial TravelIntent instantiation...")
    # Should NOT raise ValidationError now
    t = TravelIntent(destination="Paris, France")
    assert t.destination == "Paris, France"
    assert t.budget == 0.0
    assert t.is_complete() is False
    print("  OK: Partial TravelIntent works")

    t2 = TravelIntent(destination="London", budget=500, duration_days=5)
    assert t2.is_complete() is True
    print("  OK: Complete TravelIntent works")

def test_robust_budget_parsing():
    print("\nTesting robust budget parsing...")
    assert parse_budget("3000") == 3000.0
    assert parse_budget("$3,000") == 3000.0
    assert parse_budget("3000 USD") == 3000.0
    assert parse_budget("USD 3000") == 3000.0
    assert parse_budget("CHF 2500.50") == 2500.50
    assert parse_budget("5k") == 5000.0
    assert parse_budget("1.5M") == 1500000.0
    assert parse_budget("  ") is None
    assert parse_budget("abc") is None
    print("  OK: Robust budget parsing works")

def test_date_parsing_clarity():
    print("\nTesting date parsing heuristics...")
    # Non-ambiguous
    assert parse_date("15/06/2025").month == 6
    assert parse_date("06/15/2025").month == 6
    # Ambiguous - should follow US-first fallback (Dec 11)
    d = parse_date("12/11/2025")
    assert d.month == 12
    assert d.day == 11
    print("  OK: Date parsing heuristics work")

def test_log_redaction():
    print("\nTesting log redaction...")
    logger = get_logger("test")
    # Capture stdout
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)
    
    # We need to set the level to ensure it logs
    logger.setLevel(logging.DEBUG)
    
    log_with_context(logger, logging.INFO, "Testing redaction", api_key="secret-123", user="test-user")
    
    output = log_capture.getvalue()
    assert "secret-123" not in output
    assert "***REDACTED***" in output
    assert "test-user" in output
    print("  OK: Log redaction works")

if __name__ == "__main__":
    try:
        test_partial_travel_intent()
        test_robust_budget_parsing()
        test_date_parsing_clarity()
        test_log_redaction()
        print("\nALL FIX VERIFICATION TESTS PASSED ✓")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
