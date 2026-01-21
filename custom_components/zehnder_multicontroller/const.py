"""Constants for Zehnder Multicontroller."""
from __future__ import annotations

from homeassistant.const import Platform

# Base component constants
NAME = "Zehnder Multicontroller"
DOMAIN = "zehnder_multicontroller"
VERSION = "0.2.4"
ATTRIBUTION = "Data provided by Zehnder Multicontroller Integration"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 120
