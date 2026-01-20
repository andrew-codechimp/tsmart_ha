"""Diagnostics support for T-Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .common import TSmartConfigEntry

TO_REDACT = {"ip_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TSmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.device

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "version": entry.version,
        },
        "device": {
            "firmware_name": device.firmware_name,
            "firmware_version": device.firmware_version,
            "power": device.power,
            "mode": device.mode.name if device.mode is not None else None,
            "setpoint": device.setpoint,
            "temperature_average": device.temperature_average,
            "temperature_high": device.temperature_high,
            "temperature_low": device.temperature_low,
            "relay": device.relay,
            "error_e01": device.error_e01,
            "error_e01_count": device.error_e01_count,
            "error_e02": device.error_e02,
            "error_e02_count": device.error_e02_count,
            "error_e03": device.error_e03,
            "error_e03_count": device.error_e03_count,
            "error_e04": device.error_e04,
            "error_e04_count": device.error_e04_count,
            "error_e05": device.error_e05,
            "error_e05_count": device.error_e05_count,
            "warning_w01": device.warning_w01,
            "warning_w01_count": device.warning_w01_count,
            "warning_w02": device.warning_w02,
            "warning_w02_count": device.warning_w02_count,
            "warning_w03": device.warning_w03,
            "warning_w03_count": device.warning_w03_count,
            "request_successful": device.request_successful,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "temperature_mode": coordinator.temperature_mode,
        },
    }
