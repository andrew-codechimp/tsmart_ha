"""Regression tests for T-Smart diagnostics."""

import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from custom_components.t_smart.common import TSmartData
from custom_components.t_smart.diagnostics import async_get_config_entry_diagnostics
from custom_components.t_smart.tsmart import (
    TSmart,
    TSmartClock,
    TSmartInvalidResponseError,
    TSmartMode,
    TSmartSmartState,
    TSmartStatus,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


class TestDiagnostics(IsolatedAsyncioTestCase):
    """Check diagnostics before setup and after runtime data is removed."""

    async def test_before_setup(self) -> None:
        """Return the setup failure state without accessing runtime data."""
        entry = Mock(spec=ConfigEntry, state=ConfigEntryState.SETUP_RETRY)

        result = await async_get_config_entry_diagnostics(
            Mock(spec=HomeAssistant), entry
        )

        assert result == {"state": ConfigEntryState.SETUP_RETRY.value}

    async def test_after_unload(self) -> None:
        """Return the unloaded state after runtime data is deleted."""
        entry = Mock(spec=ConfigEntry, state=ConfigEntryState.NOT_LOADED)
        entry.runtime_data = object()
        del entry.runtime_data

        result = await async_get_config_entry_diagnostics(
            Mock(spec=HomeAssistant), entry
        )

        assert result == {"state": ConfigEntryState.NOT_LOADED.value}


class TestLoadedDiagnostics(IsolatedAsyncioTestCase):
    """Keep normal diagnostics available when the optional clock read fails."""

    def setUp(self) -> None:
        """Provide a loaded entry with cached status and a readable clock."""
        self.device = Mock(
            spec=TSmart, firmware_name="Boiler", firmware_version="1.2.3"
        )
        self.device.async_clock_read = AsyncMock(
            return_value=TSmartClock(day_of_week=1, hour=14, minute=5, second=9)
        )
        status = TSmartStatus(
            power=True,
            temperature_average=50,
            temperature_high=55,
            temperature_low=45,
            setpoint=60,
            mode=TSmartMode.MANUAL,
            smart_state=TSmartSmartState.IDLE,
            relay=False,
            e01=False,
            e01_count=0,
            e02=False,
            e02_count=0,
            e03=False,
            e03_count=0,
            e04=False,
            e04_count=0,
            e05=False,
            e05_count=0,
            w01=False,
            w01_count=0,
            w02=False,
            w02_count=0,
            w03=False,
            w03_count=0,
        )
        self.entry = Mock(
            spec=ConfigEntry,
            title="Water heater",
            data={"ip_address": "192.0.2.10"},
            version=3,
            runtime_data=TSmartData(device=self.device, coordinator=Mock(data=status)),
        )
        self.hass = Mock(spec=HomeAssistant)

    async def test_readable_clock(self) -> None:
        """Format the weekday and zero-padded clock without inventing a date."""
        result = await async_get_config_entry_diagnostics(self.hass, self.entry)

        assert result["device"]["clock"] == {"time": "Monday 14:05:09"}
        self.device.async_clock_read.assert_awaited_once()
        assert result["device"]["temperature_high"] == 55
        assert "192.0.2.10" not in json.dumps(result)

    async def test_clock_errors_preserve_data(self) -> None:
        """Retain all other fields and redact error messages containing addresses."""
        expected = await async_get_config_entry_diagnostics(self.hass, self.entry)
        expected["device"].pop("clock")
        for error in (
            TimeoutError(),
            ConnectionRefusedError(),
            OSError("Cannot reach 192.0.2.10"),
            TSmartInvalidResponseError("Invalid response from 192.0.2.10"),
        ):
            with self.subTest(error=type(error).__name__):
                self.device.async_clock_read.side_effect = error

                result = await async_get_config_entry_diagnostics(self.hass, self.entry)

                assert result["device"].pop("clock") == {"error": type(error).__name__}
                assert result == expected
                assert "192.0.2.10" not in json.dumps(result)

    async def test_invalid_clock_values(self) -> None:
        """Keep diagnostics usable when the device returns invalid time fields."""
        for clock in (
            TSmartClock(day_of_week=0, hour=14, minute=5, second=9),
            TSmartClock(day_of_week=8, hour=14, minute=5, second=9),
            TSmartClock(day_of_week=1, hour=24, minute=5, second=9),
            TSmartClock(day_of_week=1, hour=14, minute=60, second=9),
            TSmartClock(day_of_week=1, hour=14, minute=5, second=60),
        ):
            with self.subTest(clock=clock):
                self.device.async_clock_read.return_value = clock

                result = await async_get_config_entry_diagnostics(self.hass, self.entry)

                assert result["device"]["clock"] == {"error": "ValueError"}
                assert result["device"]["temperature_high"] == 55
