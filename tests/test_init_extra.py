"""Tests for integration setup/migration/unload flows."""
from __future__ import annotations

import pytest
import importlib

integ = importlib.import_module("custom_components.zehnder_multicontroller")
from custom_components.zehnder_multicontroller.const import VERSION, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry


class DummyEntity:
    def __init__(self, entity_id, config_entry_id, domain):
        self.entity_id = entity_id
        self.config_entry_id = config_entry_id
        self.domain = domain


@pytest.mark.asyncio
async def test_async_migrate_entry_removes_climate(monkeypatch):
    # Build a fake registry with mixed entities
    reg = type("R", (), {})()
    reg.entities = {
        "climate.foo": DummyEntity("climate.foo", "e1", "climate"),
        "sensor.bar": DummyEntity("sensor.bar", "e1", "sensor"),
    }

    removed = []

    def async_remove(entity_id):
        removed.append(entity_id)

    reg.async_remove = async_remove

    monkeypatch.setattr("homeassistant.helpers.entity_registry.async_get", lambda hass: reg)

    class DummyHass:
        def __init__(self):
            self.config_entries = type("C", (), {})()

        config_entries = None

    hass = DummyHass()

    class Entry:
        def __init__(self):
            self.entry_id = "e1"
            self.data = {"integration_version": "0.0.0"}

    entry = Entry()

    # Monkeypatch async_update_entry so we can observe it's called
    called = {}

    def async_update_entry(*args, **kwargs):
        # handle being bound as a method; accept positional or keyword 'data'
        if "data" in kwargs:
            called["updated"] = kwargs["data"]
        elif len(args) >= 2:
            called["updated"] = args[1]
        else:
            called["updated"] = None

    hass.config_entries = type("C", (), {"async_update_entry": async_update_entry})()

    # Call the coroutine
    await integ.async_migrate_entry(hass, entry)

    assert "climate.foo" in removed
    assert called.get("updated") is not None
    assert called["updated"].get("integration_version") == VERSION


@pytest.mark.asyncio
async def test_async_setup_and_unload(monkeypatch):
    # Prepare a fake RainmakerAPI that connects and a simple coordinator
    class FakeAPI:
        def __init__(self, *args, **kwargs):
            pass

        async def async_connect(self):
            return None

    class FakeCoordinator:
        def __init__(self, hass, api, entry):
            self.data = {}

        async def async_config_entry_first_refresh(self):
            return None

    # Prevent migration from touching the real entity registry
    async def _noop_migrate(hass, entry):
        return None
    monkeypatch.setattr(integ, "async_migrate_entry", _noop_migrate)

    # The async_setup_entry performs local imports; insert fake submodules
    import sys
    import types

    api_mod = types.ModuleType("custom_components.zehnder_multicontroller.api")
    api_mod.RainmakerAPI = FakeAPI
    coord_mod = types.ModuleType("custom_components.zehnder_multicontroller.coordinator")
    coord_mod.RainmakerCoordinator = FakeCoordinator
    sys.modules["custom_components.zehnder_multicontroller.api"] = api_mod
    sys.modules["custom_components.zehnder_multicontroller.coordinator"] = coord_mod

    class DummyHass:
        def __init__(self):
            self.data = {}
            self.config_entries = type("C", (), {})()

        async def async_forward(self, entry, platforms):
            return None

    hass = DummyHass()
    # stub config_entries behaviors used in async_setup_entry/unload
    async def _forward(entry, platforms):
        return None

    async def _unload(entry, platforms):
        return True

    hass.config_entries.async_forward_entry_setups = _forward
    hass.config_entries.async_unload_platforms = _unload

    # include integration_version so migration is skipped inside setup
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "h", "integration_version": VERSION}, entry_id="e1")

    result = await integ.async_setup_entry(hass, entry)
    assert result is True
    assert DOMAIN in hass.data

    unloaded = await integ.async_unload_entry(hass, entry)
    assert unloaded is True
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
