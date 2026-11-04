"""Diagnostics support for T-Smart."""

from __future__ import annotations

from calendar import day_name
from datetime import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .common import TSmartConfigEntry
from .tsmart import TSmartClock, TSmartError

TO_REDACT = {"ip_address"}


def _format_clock(clock: TSmartClock) -> str:
    """Format a valid device weekday and time without adding a date."""
    if not 1 <= clock.day_of_week <= 7:
        message = "Invalid clock day of week"
        raise ValueError(message)
    clock_time = time(clock.hour, clock.minute, clock.second)
    return f"{day_name[clock.day_of_week - 1]} {clock_time.isoformat()}"


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: TSmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if not hasattr(entry, "runtime_data"):
        return {"state": entry.state.value}

    device = entry.runtime_data.device
    data = entry.runtime_data.coordinator.data

    clock_data: dict[str, str]
    try:
        clock = await device.async_clock_read()
        formatted_clock = _format_clock(clock)
    except (OSError, TSmartError, ValueError) as err:
        clock_data = {"error": type(err).__name__}
    else:
        clock_data = {"time": formatted_clock}

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "version": entry.version,
        },
        "device": {
            "firmware_name": device.firmware_name,
            "firmware_version": device.firmware_version,
            "clock": clock_data,
            "power": data.power,
            "mode": data.mode.name if data.mode is not None else None,
            "setpoint": data.setpoint,
            "temperature_average": data.temperature_average,
            "temperature_high": data.temperature_high,
            "temperature_low": data.temperature_low,
            "relay": data.relay,
            "e01": data.e01,
            "e01_count": data.e01_count,
            "e02": data.e02,
            "e02_count": data.e02_count,
            "e03": data.e03,
            "e03_count": data.e03_count,
            "e04": data.e04,
            "e04_count": data.e04_count,
            "e05": data.e05,
            "e05_count": data.e05_count,
            "w01": data.w01,
            "w01_count": data.w01_count,
            "w02": data.w02,
            "w02_count": data.w02_count,
            "w03": data.w03,
            "w03_count": data.w03_count,
        },
    }
