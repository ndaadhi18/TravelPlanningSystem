"""
FastAPI dependency injection for core services.
"""

from typing import Annotated

from fastapi import Depends

from backend.core.settings import Settings, get_settings

# Type alias for injecting settings into route handlers
SettingsDep = Annotated[Settings, Depends(get_settings)]
