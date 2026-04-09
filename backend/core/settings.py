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
    groq_api_key: str = Field(
        ..., 
        description="Groq API key for LLM access",
        json_schema_extra={"repr": False},
    )
    groq_model_name: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model to use for agent reasoning",
    )

    # ─── MCP Server ─────────────────────────────────────────────────────
    mcp_server_host: str = Field(default="localhost", description="MCP server hostname")
    mcp_server_port: int = Field(default=8001, description="MCP server port")

    # ─── Amadeus ────────────────────────────────────────────────────────
    amadeus_client_id: Optional[str] = Field(
        default=None, 
        description="Amadeus API client ID",
        json_schema_extra={"repr": False},
    )
    amadeus_client_secret: Optional[str] = Field(
        default=None, 
        description="Amadeus API client secret",
        json_schema_extra={"repr": False},
    )
    amadeus_hostname: Literal["test", "production"] = Field(
        default="test", description="Amadeus environment (test or production)"
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
    def amadeus_configured(self) -> bool:
        """
        Check if Amadeus credentials are validly configured.
        
        Treats None, empty strings, or common placeholders as unconfigured.
        """
        placeholders = {"xxxxxxxxxxxxx", "your_id_here", "your_secret_here", ""}
        
        id_val = (self.amadeus_client_id or "").strip()
        secret_val = (self.amadeus_client_secret or "").strip()
        
        if not id_val or not secret_val:
            return False
            
        if id_val.lower() in placeholders or secret_val.lower() in placeholders:
            return False
            
        # Also check if they start with 'xxx' which is common for placeholders
        if id_val.lower().startswith("xxx") or secret_val.lower().startswith("xxx"):
            return False
            
        return True


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure only one Settings instance exists,
    avoiding repeated .env file reads.
    """
    return Settings()
