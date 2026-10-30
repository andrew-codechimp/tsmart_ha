"""Tests for restart, time synchronization, and smart reset buttons."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from custom_components.t_smart.tsmart import TSmartInvalidResponseError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_device", "button_platform")

RESTART_ENTITY_ID = "button.water_heater_restart"
TIMESYNC_ENTITY_ID = "button.water_heater_synchronise_time"
SMART_RESET_ENTITY_ID = "button.water_heater_reset_smart_mode"

BUTTON_CASES = [
    pytest.param(RESTART_ENTITY_ID, "async_restart", (1000,), id="restart"),
    pytest.param(TIMESYNC_ENTITY_ID, "async_timesync", (), id="timesync"),
    pytest.param(SMART_RESET_ENTITY_ID, "async_smart_reset", (), id="smart-reset"),
]


@pytest.fixture
def button_platform() -> Generator[None]:
    """Load only buttons for these tests."""
    with patch("custom_components.t_smart.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.usefixtures("enable_all_entities")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot button state, metadata, and device associations."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("entity_id", [TIMESYNC_ENTITY_ID, SMART_RESET_ENTITY_ID])
async def test_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Keep time synchronization and smart reset disabled by default."""
    await setup_integration(hass, mock_config_entry)
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get(RESTART_ENTITY_ID).disabled_by is None


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize(("entity_id", "method", "arguments"), BUTTON_CASES)
async def test_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    entity_id: str,
    method: str,
    arguments: tuple[int, ...],
) -> None:
    """Send the matching device command through Home Assistant's button action."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    getattr(mock_device, method).assert_awaited_once_with(*arguments)
    assert hass.states.get(entity_id).state == dt_util.utcnow().isoformat()


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize(("entity_id", "method", "arguments"), BUTTON_CASES)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_press_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    *,
    entity_id: str,
    method: str,
    arguments: tuple[int, ...],
    exception: Exception,
) -> None:
    """Propagate command failures to the action caller."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_device, method).side_effect = exception
    with pytest.raises(type(exception)):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    getattr(mock_device, method).assert_awaited_once_with(*arguments)


async def test_unavailable_button(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Do not send a restart command while the thermostat is unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_device.async_get_status.side_effect = TimeoutError
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(RESTART_ENTITY_ID).state == STATE_UNAVAILABLE
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: RESTART_ENTITY_ID}, blocking=True
    )
    mock_device.async_restart.assert_not_awaited()
