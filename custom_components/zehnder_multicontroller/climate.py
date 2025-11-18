"""Climate platform for Zehnder Multicontroller."""
from __future__ import annotations

from typing import Any
import logging
from functools import cached_property

from homeassistant.components.climate import ClimateEntity, HVACMode, ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_FAN_NAMES = ["Away", "Low", "Medium", "High"]

class ZehnderClimate(CoordinatorEntity, ClimateEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node_id: str,
        node_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node_id = node_id
        self._node_name = node_name
        self._attr_name = node_name
        self._unique_id = f"{entry_id}_{node_id}_climate"

        try:
            self._attr_temperature_unit = coordinator.hass.config.units.temperature_unit
        except AttributeError:
            self._attr_temperature_unit = "°C"

        # Initialize fan names based on fan_speed bounds
        self._fan_names = self._initialize_fan_names()

        _LOGGER.debug(
            "Creating ZehnderClimate for node %s with fan names: %s", node_id, self._fan_names
        )

        self._attr_supported_features = self.get_supported_features()

    def _initialize_fan_names(self) -> list[str]:
        """Initialize fan mode names based on fan_speed bounds."""
        node_data = self.coordinator.data.get(self._node_id, {})
        
        if "fan_speed" not in node_data:
            return DEFAULT_FAN_NAMES
        
        bounds = node_data["fan_speed"].get("bounds", {})
        min_val = bounds.get("min", 0)
        max_val = bounds.get("max", 3)
        
        # Calculate number of levels
        num_levels = int(max_val - min_val) + 1
        
        # Check if default names match the number of levels
        if num_levels == len(DEFAULT_FAN_NAMES):
            return DEFAULT_FAN_NAMES
        
        # Generate numeric names if counts don't match
        return [str(i) for i in range(min_val, max_val + 1)]

    @cached_property
    def unique_id(self) -> str | None:
        return self._unique_id

    @cached_property
    def name(self) -> str | None:
        return self._attr_name

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._node_id)},
            name=self._node_name,
            manufacturer="ESP RainMaker",
        )

    @cached_property
    def current_temperature(self) -> float | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        for param, meta in node_data.items():
            if param.lower() == "temp":
                return meta.get("value")
        return None

    @cached_property
    def target_temperature(self) -> float | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        for param, meta in node_data.items():
            if param.lower() == "temp_setpoint":
                return meta.get("value")
        return None

    @cached_property
    def hvac_modes(self) -> list[HVACMode]:
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @cached_property
    def hvac_mode(self) -> HVACMode | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        season = None
        enabled = None
        for param, meta in node_data.items():
            if param.lower() == "season":
                season = meta.get("value")
            elif param.lower() == "radiant_enabled":
                enabled = meta.get("value")
        if not enabled:
            return HVACMode.OFF
        if season == 1:
            return HVACMode.HEAT
        if season == 2:
            return HVACMode.COOL
        return None

    def get_supported_features(self) -> ClimateEntityFeature:
        features_flag = ClimateEntityFeature(0)
        node_data = self.coordinator.data.get(self._node_id, {})

        has_temp_setpoint = "temp_setpoint" in node_data and "write" in node_data["temp_setpoint"].get("properties", [])
        if has_temp_setpoint:
            features_flag |= ClimateEntityFeature.TARGET_TEMPERATURE

        has_fan = "fan_speed" in node_data and "write" in node_data["fan_speed"].get("properties", [])
        if has_fan:
            features_flag |= ClimateEntityFeature.FAN_MODE

        _LOGGER.debug(
            "ZehnderClimate(%s) params keys=%s -> features=%s",
            self._node_id,
            list(node_data.keys()),
            features_flag,
        )

        return features_flag

    def _handle_coordinator_update(self) -> None:
        try:
            self._attr_supported_features = self.get_supported_features()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception(
                "Failed to update supported features for %s", self._node_id
            )
        super()._handle_coordinator_update()

    @property
    def fan_modes(self) -> list[str] | None:
        return self._fan_names

    @property
    def fan_mode(self) -> str | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        if "fan_speed" not in node_data:
            return None
        val = node_data["fan_speed"].get("value")
        if val is None:
            return None
        level = int(val)
        
        if 0 <= level < len(self._fan_names):
            return self._fan_names[level]
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        try:
            await self.coordinator.api.async_set_param(
                self._node_id, "temp_setpoint", temperature
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set temperature on %s", self._node_id)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        try:
            if hvac_mode == HVACMode.OFF.value:
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", False
                )
            elif hvac_mode == HVACMode.HEAT.value:
                await self.coordinator.api.async_set_param(self._node_id, "season", 1)
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", True
                )
            elif hvac_mode == HVACMode.COOL.value:
                await self.coordinator.api.async_set_param(self._node_id, "season", 2)
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", True
                )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set hvac mode on %s", self._node_id)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            if fan_mode not in self._fan_names:
                _LOGGER.warning("Unknown fan mode: %s", fan_mode)
                return
            level = self._fan_names.index(fan_mode)
            await self.coordinator.api.async_set_param(
                self._node_id, "fan_speed", level
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set fan mode on %s", self._node_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    _LOGGER.info("Setting up climate platform for entry %s", entry.entry_id)
    
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.error(
            "No entry data found for %s, aborting climate setup", entry.entry_id
        )
        return
    
    coordinator = entry_data["coordinator"]
    _LOGGER.debug("Coordinator data contains %d nodes", len(coordinator.data))

    entities: list[ZehnderClimate] = []
    registry = er.async_get(hass)
    
    for node_id, params in coordinator.data.items():
        _LOGGER.debug("Checking node %s for climate entity creation", node_id)
        _LOGGER.debug("Node %s params: %s", node_id, list(params.keys()))
        
        if "temp" not in params:
            _LOGGER.debug("Node %s does not have 'temp' parameter, skipping", node_id)
            continue

        unique_id = f"{entry.entry_id}_{node_id}_climate"

        if registry.async_get_entity_id("climate", DOMAIN, unique_id) is not None:
            _LOGGER.debug(
                "Skipping climate entity for node %s because unique_id %s is already registered",
                node_id,
                unique_id,
            )
            continue

        node_name = params.get("Name", {}).get("value", node_id)
        _LOGGER.info("Creating climate entity for node %s (name: %s)", node_id, node_name)
        entities.append(ZehnderClimate(coordinator, entry.entry_id, node_id, node_name))

    _LOGGER.info("Adding %d climate entities", len(entities))
    async_add_entities(entities, True)
    _LOGGER.info("Climate platform setup completed")
