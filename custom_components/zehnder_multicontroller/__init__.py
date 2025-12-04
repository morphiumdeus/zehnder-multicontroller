"""Zehnder Multicontroller integration (custom_component for HACS)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .const import PLATFORMS
from .const import VERSION

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove and recreate climate entities on version changes."""
    entity_registry = er.async_get(hass)

    # Get the stored version from entry data, default to "0.0.0" if not present
    stored_version = entry.data.get("integration_version", "0.0.0")

    # Check if migration is needed
    if stored_version != VERSION:
        _LOGGER.info(
            "Version changed from %s to %s, recreating climate entities",
            stored_version,
            VERSION,
        )

        # Remove ALL climate entities for this integration
        entities_to_remove = []
        for entity in entity_registry.entities.values():
            if entity.config_entry_id == entry.entry_id :
                #if entity.domain == "climate" or entity not in entry.data:
                entities_to_remove.append(entity.entity_id)

        for entity_id in entities_to_remove:
            entity_registry.async_remove(entity_id)
            _LOGGER.debug("Removed climate entity for recreation: %s", entity_id)

        # Update the stored version
        new_data = {**entry.data, "integration_version": VERSION}
        hass.config_entries.async_update_entry(entry, data=new_data)
        _LOGGER.info("Climate entities removed, will be recreated with new version")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Zehnder Multicontroller config entry.

    Creates the API object, data coordinator and forwards platform setups.
    """
    _LOGGER.info(
        "Setting up Zehnder Multicontroller integration for entry %s",
        entry.entry_id,
    )

    # Perform migration if needed
    await async_migrate_entry(hass, entry)

    data = entry.data
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")

    # Import API and coordinator lazily to avoid requiring optional
    # dependencies (like `rainmaker-http`) at import time when the
    # config flow UI is loaded
    from .api import RainmakerAPI
    from .coordinator import RainmakerCoordinator

    api = RainmakerAPI(hass, host, username, password)
    try:
        _LOGGER.debug("Attempting to connect to Rainmaker API...")
        await api.async_connect()
        _LOGGER.info("Successfully connected to Rainmaker API")
    except Exception as err:
        _LOGGER.error("Failed to connect to Rainmaker: %s", err)
        raise ConfigEntryNotReady from err

    coordinator = RainmakerCoordinator(hass, api, entry)
    # Fetch initial data so platforms have data when they are first added
    _LOGGER.debug("Fetching initial data from coordinator...")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Initial data fetched: %d nodes found", len(coordinator.data))

    # Store runtime-only references
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    _LOGGER.info("Forwarding setup to platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Platform setup completed for entry %s", entry.entry_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Remove runtime references if they exist
        domain_data = hass.data.get(DOMAIN)
        if domain_data and entry.entry_id in domain_data:
            domain_data.pop(entry.entry_id)
    return unload_ok
