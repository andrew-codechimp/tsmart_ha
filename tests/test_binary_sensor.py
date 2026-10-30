"""Tests for relay, alarm, warning, and anti-legionella binary sensors."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from custom_components.t_smart.tsmart import TSmartMode
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_device", "binary_sensor_platform")

RELAY_ENTITY_ID = "binary_sensor.water_heater_relay"
ANTI_LEGIONELLA_ENTITY_ID = "binary_sensor.water_heater_anti_legionella"
ERROR_ENTITY_ID = "binary_sensor.water_heater_error"
WARNING_ENTITY_ID = "binary_sensor.water_heater_warning"


@pytest.fixture
def binary_sensor_platform() -> Generator[None]:
    """Load only binary sensors for these tests."""
    with patch("custom_components.t_smart.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("enable_all_entities")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all binary sensor states, attributes, and metadata."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "suffix",
    [
        pytest.param("e01_broken_sensors", id="e01"),
        pytest.param("e02_overheating", id="e02"),
        pytest.param("e03_dry_heating", id="e03"),
        pytest.param("e04_serial_comm_st_error", id="e04"),
        pytest.param("e05_serial_comm_esp_error", id="e05"),
        pytest.param("w01_bad_high_sensor", id="w01"),
        pytest.param("w02_bad_low_sensor", id="w02"),
        pytest.param("w03_long_heating", id="w03"),
    ],
)
async def test_alarm_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    suffix: str,
) -> None:
    """Keep individual diagnostic alarms disabled until the user enables them."""
    await setup_integration(hass, mock_config_entry)
    entity_id = f"binary_sensor.water_heater_{suffix}"
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("relay", "expected"),
    [pytest.param(True, STATE_ON, id="on"), pytest.param(False, STATE_OFF, id="off")],
)
async def test_relay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    relay: bool,
    expected: str,
) -> None:
    """Reflect the reported relay state independently of the thermostat mode."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, relay=relay
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(RELAY_ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(TSmartMode.ANTI_LEGIONELLA, STATE_ON, id="running"),
        pytest.param(TSmartMode.MANUAL, STATE_OFF, id="idle"),
    ],
)
async def test_anti_legionella(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mode: TSmartMode,
    expected: str,
) -> None:
    """Report anti-legionella activity only in its dedicated mode."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=mode
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ANTI_LEGIONELLA_ENTITY_ID).state == expected


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize(
    ("flag", "suffix", "alarm_mode"),
    [
        pytest.param("e01", "e01_broken_sensors", TSmartMode.CRITICAL, id="e01"),
        pytest.param("e02", "e02_overheating", TSmartMode.CRITICAL, id="e02"),
        pytest.param("e03", "e03_dry_heating", TSmartMode.CRITICAL, id="e03"),
        pytest.param("e04", "e04_serial_comm_st_error", TSmartMode.CRITICAL, id="e04"),
        pytest.param("e05", "e05_serial_comm_esp_error", TSmartMode.CRITICAL, id="e05"),
        pytest.param("w01", "w01_bad_high_sensor", TSmartMode.LIMITED, id="w01"),
        pytest.param("w02", "w02_bad_low_sensor", TSmartMode.LIMITED, id="w02"),
        pytest.param("w03", "w03_long_heating", TSmartMode.LIMITED, id="w03"),
    ],
)
@pytest.mark.parametrize(
    ("mode", "flag_value", "expected"),
    [
        pytest.param("alarm", True, STATE_ON, id="active"),
        pytest.param("alarm", False, STATE_OFF, id="clear"),
        pytest.param("manual", True, STATE_OFF, id="inactive-mode"),
    ],
)
async def test_individual_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    flag: str,
    suffix: str,
    alarm_mode: TSmartMode,
    mode: str,
    flag_value: bool,
    expected: str,
) -> None:
    """Gate each alarm by its flag and mode while retaining its occurrence count."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value,
        **{
            "mode": {"alarm": alarm_mode, "manual": TSmartMode.MANUAL}[mode],
            flag: flag_value,
            f"{flag}_count": 7,
        },
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(f"binary_sensor.water_heater_{suffix}")
    assert state.state == expected
    assert state.attributes["count"] == 7


@pytest.mark.parametrize(
    ("mode", "entity_id", "summary"),
    [
        pytest.param(
            TSmartMode.CRITICAL,
            ERROR_ENTITY_ID,
            "E01 - Broken sensors, E02 - Overheating, E03 - Dry heating, E04 - Serial Comm ST error, E05 - Serial Comm ESP error",
            id="errors",
        ),
        pytest.param(
            TSmartMode.LIMITED,
            WARNING_ENTITY_ID,
            "W01 - Bad High Sensor, W02 - Bad Low Sensor, W03 - Long heating",
            id="warnings",
        ),
    ],
)
async def test_alarm_summary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    mode: TSmartMode,
    entity_id: str,
    summary: str,
) -> None:
    """Combine all active alarms into their readable summary without a trailing comma."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value,
        mode=mode,
        e01=True,
        e02=True,
        e03=True,
        e04=True,
        e05=True,
        w01=True,
        w02=True,
        w03=True,
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["Summary"] == summary


@pytest.mark.usefixtures("enable_all_entities")
async def test_poll_failure_recovery(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Make binary sensors unavailable on failure and restore their states on recovery."""
    await setup_integration(hass, mock_config_entry)
    initial = {
        state.entity_id: state.state for state in hass.states.async_all("binary_sensor")
    }
    mock_device.async_get_status.side_effect = TimeoutError
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert {state.state for state in hass.states.async_all("binary_sensor")} == {
        STATE_UNAVAILABLE
    }

    mock_device.async_get_status.side_effect = None
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert {
        state.entity_id: state.state for state in hass.states.async_all("binary_sensor")
    } == initial


async def test_poll_updates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Update relay and alarm states and summaries when the reported mode changes."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value,
        relay=False,
        mode=TSmartMode.CRITICAL,
        e02=True,
        e02_count=3,
    )
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(RELAY_ENTITY_ID).state == STATE_OFF
    assert hass.states.get(ERROR_ENTITY_ID).state == STATE_ON
    assert hass.states.get(ERROR_ENTITY_ID).attributes["Summary"] == "E02 - Overheating"
    assert hass.states.get(ERROR_ENTITY_ID).attributes["E02 - Count"] == 3
