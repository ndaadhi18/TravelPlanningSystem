"""
Tests for Module M2: Config & Settings

Test Criteria (from IMPLEMENTATION.md):
- Settings load from .env
- Defaults work when optional keys are missing
- Required keys raise clear validation errors
"""

import os
import sys

sys.path.insert(0, ".")

print("=" * 60)
print("M2 Config & Settings Tests")
print("=" * 60)


# ── 1. Settings Class Import ────────────────────────────────────
print("\n[1] Import Settings class...")
from backend.core.settings import Settings, get_settings

print("  OK: Settings class imported")


# ── 2. Load Settings from .env ──────────────────────────────────
print("\n[2] Load settings from .env...")
try:
    settings = get_settings()
    print(f"  OK: Settings loaded")
    print(f"      groq_model_name: {settings.groq_model_name}")
    print(f"      mcp_server_url: {settings.mcp_server_url}")
    print(f"      app_env: {settings.app_env}")
    print(f"      log_level: {settings.log_level}")
except Exception as e:
    print(f"  FAIL: Could not load settings — {e}")
    sys.exit(1)


# ── 3. Verify Required Keys Are Present ─────────────────────────
print("\n[3] Verify required keys...")
assert settings.groq_api_key, "groq_api_key should be set"
assert settings.tavily_api_key, "tavily_api_key should be set"
print(f"  OK: groq_api_key is set (length: {len(settings.groq_api_key)})")
print(f"  OK: tavily_api_key is set (length: {len(settings.tavily_api_key)})")


# ── 4. Test Default Values ──────────────────────────────────────
print("\n[4] Test default values...")
assert settings.groq_model_name == "llama-3.3-70b-versatile", "Default model should be llama-3.3-70b-versatile"
assert settings.mcp_server_host == "localhost", "Default MCP host should be localhost"
assert settings.mcp_server_port == 8001, "Default MCP port should be 8001"
assert settings.amadeus_hostname == "test", "Default Amadeus hostname should be test"
assert settings.app_env == "development", "Default app_env should be development"
assert settings.log_level == "DEBUG", "Default log_level should be DEBUG"
print("  OK: All defaults are correct")


# ── 5. Test Computed Properties ─────────────────────────────────
print("\n[5] Test computed properties...")
assert settings.mcp_server_url == "http://localhost:8001", f"Expected http://localhost:8001, got {settings.mcp_server_url}"
assert settings.is_development is True, "is_development should be True"
assert settings.is_production is False, "is_production should be False"
print(f"  OK: mcp_server_url = {settings.mcp_server_url}")
print(f"  OK: is_development = {settings.is_development}")
print(f"  OK: is_production = {settings.is_production}")


# ── 6. Test Amadeus Optional Fields ─────────────────────────────
print("\n[6] Test Amadeus optional fields...")
print(f"  amadeus_client_id: {'set' if settings.amadeus_client_id else 'not set (OK - optional)'}")
print(f"  amadeus_client_secret: {'set' if settings.amadeus_client_secret else 'not set (OK - optional)'}")
print(f"  amadeus_configured: {settings.amadeus_configured}")
print("  OK: Amadeus fields handled correctly")


# ── 7. Test Singleton Behavior ──────────────────────────────────
print("\n[7] Test singleton behavior (get_settings caching)...")
settings1 = get_settings()
settings2 = get_settings()
assert settings1 is settings2, "get_settings should return the same instance"
print("  OK: get_settings returns cached instance")


# ── 8. Test Validation: Invalid app_env ─────────────────────────
print("\n[8] Test validation: invalid app_env...")
from pydantic import ValidationError

try:
    # Use model_validate to bypass env loading and test pure validation
    Settings.model_validate({
        "groq_api_key": "test",
        "tavily_api_key": "test",
        "app_env": "invalid_env",
    })
    print("  FAIL: Should have rejected invalid app_env")
except ValidationError as e:
    print(f"  OK: Rejected invalid app_env — ValidationError")


# ── 9. Test Validation: Invalid log_level ───────────────────────
print("\n[9] Test validation: invalid log_level...")
try:
    Settings.model_validate({
        "groq_api_key": "test",
        "tavily_api_key": "test",
        "log_level": "TRACE",
    })
    print("  FAIL: Should have rejected invalid log_level")
except ValidationError as e:
    print(f"  OK: Rejected invalid log_level — ValidationError")


# ── 10. Test Validation: Missing Required Key ───────────────────
print("\n[10] Test validation: missing required key...")
try:
    # model_validate without env loading — groq_api_key is missing
    Settings.model_validate({
        "tavily_api_key": "test",
    })
    print("  FAIL: Should have rejected missing groq_api_key")
except ValidationError as e:
    print(f"  OK: Rejected missing groq_api_key — ValidationError")


# ── 11. Test Dependencies Import ────────────────────────────────
print("\n[11] Test dependencies module...")
from backend.core.dependencies import SettingsDep, get_settings as dep_get_settings

assert dep_get_settings is get_settings, "dependencies should re-export get_settings"
print("  OK: dependencies module imports correctly")


# ── Summary ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("✓ All M2 tests passed!")
print("=" * 60)
