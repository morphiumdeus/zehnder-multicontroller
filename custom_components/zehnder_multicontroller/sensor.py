"""Sensor platform for Zehnder Multicontroller."""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RainmakerParamSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node_id: str,
        node_name: str,
        param: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node_id = node_id
        self._node_name = node_name
        self._param = param
        self._attr_name = f"{node_name} {param}"
        self._unique_id = f"{entry_id}_{node_id}_{param}"

    @cached_property
    def name(self) -> str | None:
        return self._attr_name

    @cached_property
    def unique_id(self) -> str | None:
        return self._unique_id

    @cached_property
    def native_value(self) -> Any:
        params = self.coordinator.data.get(self._node_id, {})
        return params.get(self._param, {}).get("value")

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._node_id)},
            name=self._node_name,
            manufacturer="ESP RainMaker",
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.debug("No entry data for %s, skipping sensor setup", entry.entry_id)
        return

    coordinator: DataUpdateCoordinator = entry_data["coordinator"]

    entities: list[RainmakerParamSensor] = []
    for node_id, params in coordinator.data.items():
        node_name = params.get("Name", {}).get("value", node_id)
        for param, meta in params.items():
            # Skip schedules, config, and Name parameters
            if param == "Name" or param == "config" or "schedule" in param.lower():
                continue
            dtype = meta.get("data_type", "").lower()
            if "write" not in meta.get("properties", []) and dtype != "bool":
                entity = RainmakerParamSensor(
                    coordinator, entry.entry_id, node_id, node_name, param
                )
                # Attach simple metadata-driven attributes
                if "temp" in param.lower():
                    entity._attr_native_unit_of_measurement = "°C"
                    entity._attr_device_class = SensorDeviceClass.TEMPERATURE
                elif "humidity" in param.lower():
                    entity._attr_device_class = SensorDeviceClass.HUMIDITY

                entities.append(entity)

    async_add_entities(entities, True)
