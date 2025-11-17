"""Constants for Zehnder Multicontroller."""
from __future__ import annotations

from datetime import timedelta
from homeassistant.const import Platform

# Base component constants
NAME = "Zehnder Multicontroller"
DOMAIN = "zehnder_multicontroller"
VERSION = "0.0.6"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30
