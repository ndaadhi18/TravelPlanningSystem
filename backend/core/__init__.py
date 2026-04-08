"""
PLANIT Core — application configuration and dependencies.

Exports settings and dependency injection utilities.
"""

from backend.core.dependencies import SettingsDep
from backend.core.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
    "SettingsDep",
]
