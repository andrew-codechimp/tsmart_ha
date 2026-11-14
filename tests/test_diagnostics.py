"""Regression tests for T-Smart diagnostics."""

import json
from unittest.mock import MagicMock

import pytest
from custom_components.t_smart.diagnostics import async_get_config_entry_diagnostics
from custom_components.t_smart.tsmart import TSmartClock, TSmartInvalidResponseError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.fixture
async def diagnostics_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> MockConfigEntry:
    """Set up a device with cached status and a readable clock."""
    mock_device.firmware_name = "T-Smart"
    mock_device.async_clock_read.return_value = TSmartClock(
        day_of_week=1, hour=14, minute=5, second=9
    )
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ConfigEntryState.SETUP_RETRY, id="before-setup"),
        pytest.param(ConfigEntryState.NOT_LOADED, id="after-unload"),
    ],
)
async def test_without_runtime_data(
    hass: HomeAssistant,
    state: ConfigEntryState,
) -> None:
    """Return the setup state without accessing missing runtime data."""
    entry = MockConfigEntry(domain="t_smart", state=state)

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "state": state.value
    }


async def test_readable_clock(
    hass: HomeAssistant,
    diagnostics_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Format the weekday and zero-padded clock without inventing a date."""
    result = await async_get_config_entry_diagnostics(hass, diagnostics_entry)

    assert result["device"]["clock"] == {"time": "Monday 14:05:09"}
    mock_device.async_clock_read.assert_awaited_once()
    assert result["device"]["temperature_high"] == 55
    assert "192.0.2.10" not in json.dumps(result)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="connection-refused"),
        pytest.param(OSError("Cannot reach 192.0.2.10"), id="socket-error"),
        pytest.param(
            TSmartInvalidResponseError("Invalid response from 192.0.2.10"),
            id="invalid-response",
        ),
    ],
)
async def test_clock_errors_preserve_data(
    hass: HomeAssistant,
    diagnostics_entry: MockConfigEntry,
    mock_device: MagicMock,
    error: Exception,
) -> None:
    """Retain all other fields and redact error messages containing addresses."""
    expected = await async_get_config_entry_diagnostics(hass, diagnostics_entry)
    expected["device"].pop("clock")
    mock_device.async_clock_read.side_effect = error

    result = await async_get_config_entry_diagnostics(hass, diagnostics_entry)

    assert result["device"].pop("clock") == {"error": type(error).__name__}
    assert result == expected
    assert "192.0.2.10" not in json.dumps(result)


@pytest.mark.parametrize(
    "clock",
    [
        pytest.param(
            TSmartClock(day_of_week=0, hour=14, minute=5, second=9), id="day-zero"
        ),
        pytest.param(
            TSmartClock(day_of_week=8, hour=14, minute=5, second=9), id="day-eight"
        ),
        pytest.param(
            TSmartClock(day_of_week=1, hour=24, minute=5, second=9), id="hour"
        ),
        pytest.param(
            TSmartClock(day_of_week=1, hour=14, minute=60, second=9), id="minute"
        ),
        pytest.param(
            TSmartClock(day_of_week=1, hour=14, minute=5, second=60), id="second"
        ),
    ],
)
async def test_invalid_clock_values(
    hass: HomeAssistant,
    diagnostics_entry: MockConfigEntry,
    mock_device: MagicMock,
    clock: TSmartClock,
) -> None:
    """Keep diagnostics usable when the device returns invalid time fields."""
    mock_device.async_clock_read.return_value = clock

    result = await async_get_config_entry_diagnostics(hass, diagnostics_entry)

    assert result["device"]["clock"] == {"error": "ValueError"}
    assert result["device"]["temperature_high"] == 55
