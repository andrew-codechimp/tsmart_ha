"""Tests for temperature and smart-state sensors."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from custom_components.t_smart.const import (
    ATTR_TEMPERATURE_AVERAGE,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_LOW,
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    TEMPERATURE_MODE_AVERAGE,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from custom_components.t_smart.tsmart import (
    TSmartInvalidResponseError,
    TSmartSmartState,
)
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_device", "sensor_platform")

TEMPERATURE_ENTITY_ID = "sensor.water_heater_current_temperature"
SMART_STATE_ENTITY_ID = "sensor.water_heater_smart_state"


@pytest.fixture
def sensor_platform() -> Generator[None]:
    """Load only the sensor platform for these tests."""
    with patch("custom_components.t_smart.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("enable_all_entities")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot states, attributes, metadata, and device associations."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_smart_state_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep the diagnostic smart-state sensor disabled until the user enables it."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(SMART_STATE_ENTITY_ID)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(SMART_STATE_ENTITY_ID) is None
    assert hass.states.get(TEMPERATURE_ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, "55.0", id="default-high"),
        pytest.param({CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_HIGH}, "55.0", id="high"),
        pytest.param({CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW}, "45.0", id="low"),
        pytest.param(
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_AVERAGE}, "50.0", id="average"
        ),
    ],
)
async def test_temperature_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    options: dict[str, str],
    expected: str,
) -> None:
    """Select the configured temperature while retaining all temperature attributes."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert state.state == expected
    assert state.attributes[ATTR_TEMPERATURE_HIGH] == 55.0
    assert state.attributes[ATTR_TEMPERATURE_LOW] == 45.0
    assert state.attributes[ATTR_TEMPERATURE_AVERAGE] == 50.0


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize(
    ("smart_state", "expected"),
    [
        pytest.param(
            TSmartSmartState.UNINITIALIZED, "uninitialized", id="uninitialized"
        ),
        pytest.param(TSmartSmartState.IDLE, "idle", id="idle"),
        pytest.param(TSmartSmartState.RECORDING, "recording", id="recording"),
        pytest.param(TSmartSmartState.REPRODUCTION, "reproduction", id="reproduction"),
        pytest.param(TSmartSmartState.UNKNOWN, STATE_UNKNOWN, id="unknown"),
    ],
)
async def test_smart_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    smart_state: TSmartSmartState,
    expected: str,
) -> None:
    """Expose every known smart state and map the unknown state to unknown."""
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value, smart_state=smart_state
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(SMART_STATE_ENTITY_ID).state == expected


@pytest.mark.usefixtures("enable_all_entities")
async def test_poll_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Publish new temperatures and smart state after a successful poll."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.return_value = replace(
        mock_device.async_get_status.return_value,
        temperature_high=62.4,
        temperature_low=48.2,
        temperature_average=55.3,
        smart_state=TSmartSmartState.RECORDING,
    )

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert state.state == "62.4"
    assert state.attributes[ATTR_TEMPERATURE_HIGH] == 62.4
    assert state.attributes[ATTR_TEMPERATURE_LOW] == 48.2
    assert state.attributes[ATTR_TEMPERATURE_AVERAGE] == 55.3
    assert hass.states.get(SMART_STATE_ENTITY_ID).state == "recording"


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_poll_failure_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    exception: Exception,
) -> None:
    """Make both sensors unavailable after a failed poll and recover on success."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.side_effect = exception
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(SMART_STATE_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_device.async_get_status.side_effect = None
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "55.0"
    assert hass.states.get(SMART_STATE_ENTITY_ID).state == "uninitialized"


@pytest.mark.usefixtures("enable_all_entities")
async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Make sensors unavailable on unload while retaining their registry identities."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(SMART_STATE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_temperature"
    ) == (TEMPERATURE_ENTITY_ID)
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_smart_state"
    ) == (SMART_STATE_ENTITY_ID)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(TEMPERATURE_MODE_HIGH, 131.0, id="high"),
        pytest.param(TEMPERATURE_MODE_LOW, 113.0, id="low"),
        pytest.param(TEMPERATURE_MODE_AVERAGE, 122.0, id="average"),
    ],
)
async def test_fahrenheit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mode: str,
    expected: float,
) -> None:
    """Convert Celsius readings to Fahrenheit once, including temperature attributes."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TEMPERATURE_MODE: mode}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert float(state.state) == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.FAHRENHEIT
    assert state.attributes[ATTR_TEMPERATURE_HIGH] == 131.0
    assert state.attributes[ATTR_TEMPERATURE_LOW] == 113.0
    assert state.attributes[ATTR_TEMPERATURE_AVERAGE] == 122.0
