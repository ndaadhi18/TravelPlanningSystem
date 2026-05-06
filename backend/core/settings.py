"""
Application settings loaded from environment variables.

Uses pydantic-settings for validation and .env file support.
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the PLANIT application.
    
    Required keys must be set in .env or environment.
    Optional keys have sensible defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── LLM ────────────────────────────────────────────────────────────
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for LLM access",
        json_schema_extra={"repr": False},
    )
    openai_model_name: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for agent reasoning",
    )

    # ─── MCP Server ─────────────────────────────────────────────────────
    mcp_server_host: str = Field(default="localhost", description="MCP server hostname")
    mcp_server_port: int = Field(default=8001, description="MCP server port")

    # ─── AeroDataBox (Flight Search) ────────────────────────────────────
    aerodatabox_api_key: Optional[str] = Field(
        default=None,
        description="AeroDataBox API key via API.market for flight schedules",
        json_schema_extra={"repr": False},
    )

    # ─── Booking.com via RapidAPI (Hotel Search) ─────────────────────────
    rapidapi_key: Optional[str] = Field(
        default=None,
        description="RapidAPI key for Booking.com hotel search",
        json_schema_extra={"repr": False},
    )

    # ─── Tavily ─────────────────────────────────────────────────────────
    tavily_api_key: str = Field(
        ..., 
        description="Tavily API key for web search",
        json_schema_extra={"repr": False},
    )

    # ─── App ────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="DEBUG", description="Logging level"
    )

    # ─── Computed Properties ────────────────────────────────────────────
    @computed_field
    @property
    def mcp_server_url(self) -> str:
        """Full URL for the MCP server."""
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}"

    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"

    @computed_field
    @property
    def aerodatabox_configured(self) -> bool:
        """Check if AeroDataBox credentials are configured."""
        key = (self.aerodatabox_api_key or "").strip()
        return bool(key) and not key.lower().startswith("xxx")

    @computed_field
    @property
    def booking_com_configured(self) -> bool:
        """Check if RapidAPI / Booking.com credentials are configured."""
        key = (self.rapidapi_key or "").strip()
        return bool(key) and not key.lower().startswith("xxx")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure only one Settings instance exists,
    avoiding repeated .env file reads.
    """
    return Settings()
