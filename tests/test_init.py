"""Tests for Home Assistant setup using decoded UDP responses."""

from datetime import timedelta
from itertools import chain, repeat
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.t_smart.const import (
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    TEMPERATURE_MODE_AVERAGE,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from custom_components.t_smart.tsmart import (
    DiscoveredDevice,
    TSmartInvalidResponseError,
)
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MockUDP


@pytest.mark.parametrize(
    "platform",
    [
        pytest.param(Platform.SENSOR, id="sensor"),
        pytest.param(Platform.BINARY_SENSOR, id="binary-sensor"),
        pytest.param(Platform.CLIMATE, id="climate"),
        pytest.param(Platform.BUTTON, id="button"),
    ],
)
@pytest.mark.usefixtures("enable_all_entities")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp: MockUDP,
    snapshot: SnapshotAssertion,
    *,
    platform: Platform,
) -> None:
    """Create entities from wire responses and unload their polling coordinator."""
    device = load_json_object_fixture("device.json")
    mock_udp.recv.side_effect = [
        bytes.fromhex(device["configuration"]),
        bytes.fromhex(device["status"]),
    ]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.t_smart.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(
        hass, er.async_get(hass), snapshot, mock_config_entry.entry_id
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_udp.socket.close.call_count == 2


async def test_setup_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp: MockUDP,
) -> None:
    """Leave the entry retryable when the thermostat does not respond."""
    mock_udp.recv.side_effect = TimeoutError
    mock_udp.recvfrom.side_effect = TimeoutError
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_udp.socket.close.call_count == 2


@pytest.mark.usefixtures("mock_device")
async def test_migrate_entity_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Migrate version 1 entity IDs without losing registry identities or custom names."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=1)
    temperature = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "1234",
        config_entry=mock_config_entry,
        suggested_object_id="tank_temperature",
    )
    temperature = entity_registry.async_update_entity(
        temperature.entity_id, name="Tank temperature"
    )
    relay = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        "1234",
        config_entry=mock_config_entry,
        suggested_object_id="tank_relay",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.version == 3
    assert mock_config_entry.unique_id == "1234"
    assert (
        entity_registry.async_get(temperature.entity_id).unique_id == "1234_temperature"
    )
    assert entity_registry.async_get(temperature.entity_id).id == temperature.id
    assert entity_registry.async_get(temperature.entity_id).name == "Tank temperature"
    assert entity_registry.async_get(relay.entity_id).unique_id == "1234_relay"
    assert entity_registry.async_get(relay.entity_id).id == relay.id
    assert hass.states.get(temperature.entity_id).state == "55.0"
    assert hass.states.get(relay.entity_id).state == "on"

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(temperature.entity_id).id == temperature.id
    assert entity_registry.async_get(relay.entity_id).id == relay.id
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 18
    )


@pytest.mark.usefixtures("mock_device")
@pytest.mark.parametrize(
    "version", [pytest.param(1, id="version-1"), pytest.param(2, id="version-2")]
)
@pytest.mark.parametrize(
    ("data_options", "options", "expected_options", "expected_temperature"),
    [
        pytest.param(
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW},
            {},
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW},
            "45.0",
            id="move-low-mode",
        ),
        pytest.param(
            {},
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_AVERAGE},
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_AVERAGE},
            "50.0",
            id="preserve-existing-options",
        ),
        pytest.param({}, {}, {}, "55.0", id="no-temperature-option"),
    ],
)
async def test_migrate_temperature_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    *,
    version: int,
    data_options: dict[str, str],
    options: dict[str, str],
    expected_options: dict[str, str],
    expected_temperature: str,
) -> None:
    """Upgrade old entries with or without a saved temperature mode or registry entities."""
    original_data = dict(mock_config_entry.data)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=version,
        data={**original_data, **data_options},
        options=options,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.version == 3
    assert mock_config_entry.data == original_data
    assert mock_config_entry.options == expected_options
    assert mock_config_entry.unique_id == "1234"
    assert (
        hass.states.get("sensor.water_heater_current_temperature").state
        == expected_temperature
    )


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            ConnectionRefusedError(),
            "Connection refused by device Water heater on 192.0.2.10",
            id="refused",
        ),
        pytest.param(
            TSmartInvalidResponseError(),
            "Invalid response received from device Water heater",
            id="invalid-response",
        ),
    ],
)
async def test_configuration_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_discovery: AsyncMock,
    *,
    exception: Exception,
    reason: str,
) -> None:
    """Retry refused or invalid connections without forwarding setup to platforms."""
    mock_device.async_get_configuration.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == reason
    assert not hass.states.async_entity_ids("sensor")
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), mock_config_entry.entry_id
    )
    mock_discovery.assert_not_awaited()
    mock_device.async_get_status.assert_not_awaited()


async def test_rediscover_changed_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_discovery: AsyncMock,
) -> None:
    """Ignore other devices and reconnect to the configured thermostat at its new IP."""
    original_data = dict(mock_config_entry.data)
    configuration = mock_device.async_get_configuration.return_value
    mock_device.async_get_configuration.side_effect = chain(
        [TimeoutError()], repeat(configuration)
    )
    mock_discovery.return_value = [
        DiscoveredDevice(
            ip_address="192.0.2.30", device_id="5678", name="Other heater"
        ),
        DiscoveredDevice(
            ip_address="192.0.2.20", device_id="1234", name="Water heater"
        ),
    ]
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data == {**original_data, CONF_IP_ADDRESS: "192.0.2.20"}
    assert mock_config_entry.unique_id == "1234"
    assert mock_config_entry.runtime_data.device.ip_address == "192.0.2.20"
    assert hass.states.get("sensor.water_heater_current_temperature").state == "55.0"
    mock_discovery.assert_awaited_once_with()


async def test_rediscovery_wrong_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_discovery: AsyncMock,
) -> None:
    """Keep the configured address when discovery finds only a different thermostat."""
    original_data = dict(mock_config_entry.data)
    mock_device.async_get_configuration.side_effect = TimeoutError
    mock_discovery.return_value = [
        DiscoveredDevice(ip_address="192.0.2.30", device_id="5678", name="Other heater")
    ]
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == "Unable to connect to 192.0.2.10"
    assert mock_config_entry.data == original_data
    mock_device.async_get_status.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            ConnectionRefusedError(),
            "Connection refused by device Water heater on 192.0.2.20",
            id="refused",
        ),
        pytest.param(
            TSmartInvalidResponseError(),
            "Invalid response received from device Water heater",
            id="invalid-response",
        ),
        pytest.param(
            TimeoutError(), "Timeout connecting to device Water heater", id="timeout"
        ),
    ],
)
async def test_rediscovered_configuration_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_discovery: AsyncMock,
    *,
    exception: Exception,
    reason: str,
) -> None:
    """Leave setup retryable if reading configuration at the discovered address fails."""
    mock_device.async_get_configuration.side_effect = chain(
        [TimeoutError()], repeat(exception)
    )
    mock_discovery.return_value = [
        DiscoveredDevice(ip_address="192.0.2.20", device_id="1234", name="Water heater")
    ]
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "192.0.2.20"
    assert mock_config_entry.reason == reason
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), mock_config_entry.entry_id
    )
    mock_device.async_get_status.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            TimeoutError(),
            "Timeout trying to fetch status from Water heater",
            id="timeout",
        ),
        pytest.param(
            ConnectionRefusedError(),
            "Connection refused by device Water heater",
            id="refused",
        ),
        pytest.param(
            TSmartInvalidResponseError(),
            "Invalid response received from Water heater",
            id="invalid-response",
        ),
    ],
)
async def test_first_status_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Do not create platform entities when the first coordinator refresh fails."""
    mock_device.async_get_status.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert reason in mock_config_entry.reason
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), mock_config_entry.entry_id
    )
    mock_device.async_get_configuration.assert_awaited_once_with()
    mock_device.async_get_status.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("temperature_mode", "expected_temperature"),
    [
        pytest.param(TEMPERATURE_MODE_LOW, "45.0", id="low"),
        pytest.param(TEMPERATURE_MODE_AVERAGE, "50.0", id="average"),
    ],
)
async def test_options_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    temperature_mode: str,
    expected_temperature: str,
) -> None:
    """Reload a loaded entry through the options flow and apply the selected sensor."""
    await setup_integration(hass, mock_config_entry)
    old_coordinator = mock_config_entry.runtime_data.coordinator
    assert old_coordinator.temperature_mode == TEMPERATURE_MODE_HIGH
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_TEMPERATURE_MODE: temperature_mode}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.coordinator is not old_coordinator
    assert (
        mock_config_entry.runtime_data.coordinator.temperature_mode == temperature_mode
    )
    assert (
        hass.states.get("sensor.water_heater_current_temperature").state
        == expected_temperature
    )
    assert mock_device.async_get_configuration.await_count == 2
    assert mock_device.async_get_status.await_count == 2


@pytest.mark.usefixtures("mock_device")
async def test_unload_removes_update_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Changing options after unload must not reload an inactive entry."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        hass.config_entries.async_update_entry(
            mock_config_entry, options={CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW}
        )
        await hass.async_block_till_done()

    reload.assert_not_awaited()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_cleans_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed setup must not leave an extra update listener after a successful retry."""
    mock_config_entry.add_to_hass(hass)
    mock_device.async_get_configuration.side_effect = ConnectionRefusedError
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_device.async_get_configuration.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_device.async_get_configuration.await_count == 3
    assert mock_device.async_get_status.await_count == 2
    assert hass.states.get("sensor.water_heater_current_temperature").state == "45.0"
