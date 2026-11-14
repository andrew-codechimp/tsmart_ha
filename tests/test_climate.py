"""Tests for thermostat states, temperature selection, and climate actions."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from custom_components.t_smart.const import (
    ATTR_TEMPERATURE_AVERAGE,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_LOW,
    CONF_TEMPERATURE_MODE,
    PRESET_MANUAL,
    PRESET_SMART,
    PRESET_TIMER,
    TEMPERATURE_MODE_AVERAGE,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from custom_components.t_smart.tsmart import TSmartInvalidResponseError, TSmartMode
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_device", "climate_platform")

ENTITY_ID = "climate.water_heater"
PRESET_CASES = [
    pytest.param(PRESET_MANUAL, TSmartMode.MANUAL, id="manual"),
    pytest.param(PRESET_ECO, TSmartMode.ECO, id="eco"),
    pytest.param(PRESET_SMART, TSmartMode.SMART, id="smart"),
    pytest.param(PRESET_TIMER, TSmartMode.TIMER, id="timer"),
    pytest.param(PRESET_AWAY, TSmartMode.TRAVEL, id="away"),
    pytest.param(PRESET_BOOST, TSmartMode.BOOST, id="boost"),
]


@pytest.fixture
def climate_platform() -> Generator[None]:
    """Load only climate and skip the device's post-command settling delay."""
    with (
        patch("custom_components.t_smart.PLATFORMS", [Platform.CLIMATE]),
        patch("custom_components.t_smart.climate.AFTER_SET_SLEEP", 0),
    ):
        yield


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot thermostat state, supported actions, presets, and metadata."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("power", "relay", "expected_mode", "expected_action"),
    [
        pytest.param(True, True, HVACMode.HEAT, HVACAction.HEATING, id="heating"),
        pytest.param(True, False, HVACMode.HEAT, HVACAction.IDLE, id="idle"),
        pytest.param(False, False, HVACMode.OFF, HVACAction.OFF, id="off"),
        pytest.param(False, True, HVACMode.OFF, HVACAction.OFF, id="off-with-relay"),
    ],
)
async def test_hvac_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    power: bool,
    relay: bool,
    expected_mode: HVACMode,
    expected_action: HVACAction,
) -> None:
    """Derive HVAC mode and action from power and relay reports."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, power=power, relay=relay
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_mode
    assert state.attributes[ATTR_HVAC_ACTION] == expected_action


@pytest.mark.parametrize(("preset", "mode"), PRESET_CASES)
async def test_preset_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    preset: str,
    mode: TSmartMode,
) -> None:
    """Map each reported device mode to the corresponding Home Assistant preset."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=mode
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == preset


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(TSmartMode.CRITICAL, id="critical"),
        pytest.param(TSmartMode.LIMITED, id="limited"),
        pytest.param(TSmartMode.ANTI_LEGIONELLA, id="anti-legionella"),
        pytest.param(TSmartMode.UNKNOWN, id="unknown"),
    ],
)
async def test_special_mode_preserves_preset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mode: TSmartMode,
) -> None:
    """Retain the last regular preset during a temporary or unrecognized mode."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=TSmartMode.ECO
    )
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=mode
    )
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == PRESET_ECO


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(TEMPERATURE_MODE_HIGH, 55.0, id="high"),
        pytest.param(TEMPERATURE_MODE_LOW, 45.0, id="low"),
        pytest.param(TEMPERATURE_MODE_AVERAGE, 50.0, id="average"),
    ],
)
async def test_temperature_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mode: str,
    expected: float,
) -> None:
    """Use the configured sensor for current temperature while retaining all readings."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TEMPERATURE_MODE: mode}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == expected
    assert state.attributes[ATTR_TEMPERATURE] == 60.0
    assert state.attributes[ATTR_TEMPERATURE_HIGH] == 55.0
    assert state.attributes[ATTR_TEMPERATURE_LOW] == 45.0
    assert state.attributes[ATTR_TEMPERATURE_AVERAGE] == 50.0


@pytest.mark.parametrize(
    ("mode", "expected_power"),
    [
        pytest.param(HVACMode.HEAT, True, id="heat"),
        pytest.param(HVACMode.OFF, False, id="off"),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mode: HVACMode,
    expected_power: bool,
) -> None:
    """Send HVAC changes with the existing preset and setpoint, then poll for status."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=TSmartMode.ECO
    )
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, power=expected_power
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )
    mock_device.async_control_set.assert_awaited_once_with(
        expected_power, TSmartMode.ECO, 60.0
    )
    assert mock_device.async_get_status.await_count == 2
    assert hass.states.get(ENTITY_ID).state == mode


@pytest.mark.parametrize(
    ("service", "expected_power", "expected_mode"),
    [
        pytest.param(SERVICE_TURN_ON, True, HVACMode.HEAT, id="turn-on"),
        pytest.param(SERVICE_TURN_OFF, False, HVACMode.OFF, id="turn-off"),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    service: str,
    expected_power: bool,
    expected_mode: HVACMode,
) -> None:
    """Route standard turn-on and turn-off actions through the device control command."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, power=expected_power
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_device.async_control_set.assert_awaited_once_with(
        expected_power, TSmartMode.MANUAL, 60.0
    )
    assert hass.states.get(ENTITY_ID).state == expected_mode


@pytest.mark.parametrize(
    ("input_data", "expected_power", "expected_mode"),
    [
        pytest.param(
            {ATTR_TEMPERATURE: 65}, True, HVACMode.HEAT, id="temperature-only"
        ),
        pytest.param(
            {ATTR_TEMPERATURE: 65, ATTR_HVAC_MODE: HVACMode.HEAT},
            True,
            HVACMode.HEAT,
            id="heat",
        ),
        pytest.param(
            {ATTR_TEMPERATURE: 65, ATTR_HVAC_MODE: HVACMode.OFF},
            False,
            HVACMode.OFF,
            id="off",
        ),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    input_data: dict[str, str | int],
    expected_power: bool,
    expected_mode: HVACMode,
) -> None:
    """Send the target temperature and optional HVAC mode while retaining the preset."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=TSmartMode.ECO
    )
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, power=expected_power, setpoint=65.0
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, **input_data},
        blocking=True,
    )
    mock_device.async_control_set.assert_awaited_once_with(
        expected_power, TSmartMode.ECO, 65.0
    )
    assert mock_device.async_get_status.await_count == 2
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_mode
    assert state.attributes[ATTR_TEMPERATURE] == 65.0


@pytest.mark.parametrize(("preset", "mode"), PRESET_CASES)
@pytest.mark.parametrize(
    "power", [pytest.param(True, id="on"), pytest.param(False, id="off")]
)
async def test_set_preset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    preset: str,
    mode: TSmartMode,
    power: bool,
) -> None:
    """Change each preset while preserving power and target temperature."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, power=power
    )
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, mode=mode
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    mock_device.async_control_set.assert_awaited_once_with(power, mode, 60.0)
    assert mock_device.async_get_status.await_count == 2
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == preset


async def test_fahrenheit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Display Fahrenheit and convert action input back to Celsius for the thermostat."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 131.0
    assert state.attributes[ATTR_TEMPERATURE] == 140.0
    assert state.attributes[ATTR_TEMPERATURE_HIGH] == 131.0
    assert state.attributes[ATTR_TEMPERATURE_LOW] == 113.0
    assert state.attributes[ATTR_TEMPERATURE_AVERAGE] == 122.0

    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, setpoint=65.0
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 149.0},
        blocking=True,
    )
    mock_device.async_control_set.assert_awaited_once_with(
        True, TSmartMode.MANUAL, 65.0
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 149.0


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}, id="hvac"),
        pytest.param(
            SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 65.0}, id="temperature"
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_ECO}, id="preset"
        ),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    service: str,
    data: dict[str, str | float],
    exception: Exception,
) -> None:
    """Expose failed control commands to the action caller without polling again."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_control_set.side_effect = exception
    with pytest.raises(type(exception)):
        await hass.services.async_call(
            CLIMATE_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )
    assert mock_device.async_get_status.await_count == 1


async def test_poll_failure_recovery(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Recover the thermostat's state after a failed poll makes it unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.side_effect = TimeoutError
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_device.async_get_status.side_effect = None
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
